import re
import logging as _logging
from datetime import datetime as _dt, timedelta as _td
from core.db import Session, Watchlist, SeenItem, Download
from core.filters import apply_global_filters, get_global_filters

_log = _logging.getLogger(__name__)

# Transmission backoff: după un eșec de conectare, nu mai încercăm 2 minute
_tx_down_until: _dt | None = None
_TX_BACKOFF_SECONDS = 120


def _tx_is_up() -> bool:
    return _tx_down_until is None or _dt.utcnow() >= _tx_down_until


def _mark_tx_down():
    global _tx_down_until
    _tx_down_until = _dt.utcnow() + _td(seconds=_TX_BACKOFF_SECONDS)
    _log.warning("[TX] Transmission inaccesibil — se suspendă trimiterile pentru %ds", _TX_BACKOFF_SECONDS)


def _mark_tx_up():
    global _tx_down_until
    _tx_down_until = None


def _norm(s: str) -> str:
    """Normalizează separatorii frecvenți din titluri torrent: punct, underscore, liniuță → spațiu."""
    return re.sub(r'[._\-]', ' ', s).lower()


def _already_seen(guid: str) -> bool:
    with Session() as s:
        return s.query(SeenItem).filter_by(guid=guid).first() is not None


def _mark_seen(feed_id: int, guid: str, title: str):
    with Session() as s:
        if not s.query(SeenItem).filter_by(guid=guid).first():
            s.add(SeenItem(feed_id=feed_id, guid=guid, title=title))
            s.commit()


# Valori returnate de _send_to_transmission:
#   "ok"       — adăugat cu succes
#   "no_link"  — item fără magnet/torrent (URL streaming etc.) → marcat seen
#   "tx_down"  — Transmission inaccesibil → NU marcat seen, backoff activat
#   "error"    — altă eroare (duplicat etc.) → marcat seen pentru a evita retry infinit

def _send_to_transmission(item: dict, subdir: str | None) -> str:
    magnet = item.get("magnet") or item.get("link") or ""
    has_getter = bool(item.get("_magnet_getter"))

    if not magnet.startswith("magnet:") and has_getter:
        magnet = item["_magnet_getter"]() or ""

    torrent_url = item.get("torrent_url") or ""

    if not magnet.startswith("magnet:") and not (torrent_url and torrent_url.endswith(".torrent")):
        return "no_link"

    try:
        from transmission_rpc import Client
        from core.instance import get_instance
        from core.config import INSTANCE_ID
        inst = get_instance()
        client = Client(
            host=inst["transmission_host"],
            port=inst["transmission_port"],
            username=inst["transmission_user"],
            password=inst["transmission_pass"],
            timeout=5,
        )
        base_dir = inst["download_dir"]
        download_dir = f"{base_dir.rstrip('/')}/{subdir}" if subdir and base_dir else base_dir or None
        kwargs = {"download_dir": download_dir} if download_dir else {}

        if magnet.startswith("magnet:"):
            t = client.add_torrent(magnet, **kwargs)
        else:
            t = client.add_torrent(torrent_url, **kwargs)

        _mark_tx_up()
        with Session() as s:
            if not s.query(Download).filter_by(torrent_hash=t.hashString).first():
                s.add(Download(
                    instance_id=INSTANCE_ID,
                    torrent_hash=t.hashString,
                    title=item.get("title", ""),
                    status="queued",
                    size_bytes=item.get("size_bytes"),
                ))
                s.commit()
        return "ok"
    except Exception as ex:
        msg = str(ex).lower()
        if any(k in msg for k in ("connection", "refused", "timeout", "timed out", "unreachable", "network")):
            _mark_tx_down()
            return "tx_down"
        # Duplicat sau altă eroare Transmission — marcat seen pentru a evita retry infinit
        return "error"


def _matches_watchlist_term(title: str, entry: Watchlist) -> str | None:
    """Returns the first matching term, or None if excluded or no match."""
    t = title.lower()
    for exc in (entry.exclusions or []):
        if exc.lower() in t:
            return None
    for term in (entry.terms or []):
        if term.lower() in t:
            return term
    return None


_wl_log = _logging.getLogger("watchlist")


def run_watchlist_entry_now(entry_id: int) -> str:
    """
    Polls all relevant feeds for a specific watchlist entry.
    Pipeline: read RSS → term match → exclusions → global filters → Transmission.
    Updates last_run_at, writes WatchlistLog. Returns a human-readable summary.
    """
    from core.db import Feed, Setting, WatchlistLog
    from core.rss_parser import fetch_feed
    from core.scrapers import get_scraper

    with Session() as s:
        entry = s.query(Watchlist).filter_by(id=entry_id).first()
        if not entry:
            return "Intrare negăsită"

        terms     = [t.lower() for t in (entry.terms or [])]
        excl      = [e.lower() for e in (entry.exclusions or [])]
        subdir    = entry.download_subdir
        name      = entry.name
        feed_ids  = list(entry.feed_ids or [])
        log_level = entry.log_level or "full"

        if feed_ids:
            feeds = s.query(Feed).filter(
                Feed.id.in_(feed_ids), Feed.is_active == True
            ).all()
        else:
            feeds = s.query(Feed).filter_by(is_active=True).all()

        feed_list = [
            {"id": f.id, "name": f.name, "url": f.url,
             "source_type": f.source_type or "rss",
             "indexer_id": f.indexer_id, "categories": f.categories}
            for f in feeds
        ]
        row = s.query(Setting).filter_by(key="flaresolverr_url").first()
        flaresolverr = row.value if row and row.value else None

    global_filters = get_global_filters()
    sent = 0
    checked = 0
    blocked = 0
    tx_suspended = False
    log_entries: list[dict] = []

    for feed in feed_list:
        try:
            if feed["source_type"] == "rss":
                items = fetch_feed(feed["url"])
                cats = feed.get("categories") or []
                if cats:
                    items = [i for i in items if i.get("category") in cats]
            else:
                scraper = get_scraper(feed["indexer_id"])
                if not scraper:
                    continue
                cats = feed.get("categories") or []
                items = scraper.fetch_latest(
                    categories=cats if cats else None,
                    flaresolverr_url=flaresolverr,
                )
                for item in items:
                    if not item.get("magnet") and item.get("url"):
                        item["_magnet_getter"] = lambda url=item["url"]: scraper.get_magnet(
                            url, flaresolverr_url=flaresolverr
                        )

            for item in items:
                checked += 1
                title = item.get("title", "")
                guid  = item.get("guid") or item.get("link") or title

                if _already_seen(guid):
                    continue

                t_norm = _norm(title)

                blocked_by_excl = next((e for e in excl if _norm(e) in t_norm), None)
                if blocked_by_excl:
                    _wl_log.debug("[%s] exclus '%s': %s", name, blocked_by_excl, title)
                    if log_level in ("full", "verbose"):
                        log_entries.append({"title": title, "action": "excluded", "reason": f'excludere: "{blocked_by_excl}"'})
                    blocked += 1
                    continue

                matched_term = next((t for t in terms if _norm(t) in t_norm), None)
                if not matched_term:
                    if log_level == "verbose":
                        log_entries.append({"title": title, "action": "nomatch", "reason": "fără potrivire"})
                    continue

                passed, reason = apply_global_filters(item, global_filters)
                if not passed:
                    _wl_log.info("[%s] blocat (%s): %s", name, reason, title)
                    if log_level in ("full", "verbose"):
                        log_entries.append({"title": title, "action": "blocked", "reason": reason})
                    blocked += 1
                    continue

                # Dacă Transmission e suspendat (down), sărim trimiterile
                if not _tx_is_up():
                    if not tx_suspended:
                        tx_suspended = True
                        _wl_log.warning("[%s] Transmission suspendat — trimiterile se reiau la revenire", name)
                    if log_level in ("full", "verbose"):
                        log_entries.append({"title": title, "action": "skipped", "reason": "Transmission inaccesibil"})
                    continue

                result = _send_to_transmission(item, subdir)

                if result == "ok":
                    sent += 1
                    _mark_seen(feed["id"], guid, title)
                    _wl_log.info("[%s] ✓ trimis '%s': %s", name, matched_term, title)
                    if log_level in ("full", "sent", "verbose"):
                        log_entries.append({"title": title, "action": "sent", "reason": f'termen: "{matched_term}"'})

                elif result == "no_link":
                    # Item fără magnet/torrent (ex: link streaming) — marcat seen, nu se mai încearcă
                    _mark_seen(feed["id"], guid, title)
                    _wl_log.debug("[%s] fără link torrent (ignorat): %s", name, title)
                    if log_level in ("full", "verbose"):
                        log_entries.append({"title": title, "action": "no_link", "reason": "fără magnet/torrent"})

                elif result == "tx_down":
                    # Transmission inaccesibil — nu marcăm seen, reîncercăm la revenire
                    tx_suspended = True
                    _wl_log.warning("[%s] Transmission inaccesibil — '%s' se reîncercă", name, title)
                    if log_level in ("full", "verbose"):
                        log_entries.append({"title": title, "action": "skipped", "reason": "Transmission inaccesibil"})

                else:  # "error" — duplicat sau altă eroare Transmission
                    _mark_seen(feed["id"], guid, title)
                    _wl_log.warning("[%s] eroare Transmission (marcat seen): %s", name, title)
                    if log_level in ("full", "sent", "verbose"):
                        log_entries.append({"title": title, "action": "error", "reason": "eroare Transmission"})

        except Exception as ex:
            _wl_log.warning("[%s] eroare feed '%s': %s", name, feed.get("name", "?"), ex)

    now = _dt.utcnow()
    with Session() as s:
        entry = s.query(Watchlist).filter_by(id=entry_id).first()
        if entry:
            entry.last_run_at = now
            s.commit()
        s.add(WatchlistLog(
            watchlist_id=entry_id,
            watchlist_name=name,
            ran_at=now,
            items_checked=checked,
            items_sent=sent,
            items_blocked=blocked,
            entries=log_entries if log_level != "summary" else [],
        ))
        s.commit()

    if tx_suspended:
        return "Transmission inaccesibil — trimiterile se reiau la revenire"
    if sent > 0:
        return f"✓ {sent} torente noi trimise la Transmission"
    if checked == 0:
        return "Niciun feed activ disponibil"
    return f"Niciun rezultat nou ({checked} items verificate)"



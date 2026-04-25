import re
from core.db import Session, Watchlist, SeenItem, Download
from core.filters import apply_global_filters, get_global_filters


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


def _send_to_transmission(item: dict, subdir: str | None) -> bool:
    try:
        from transmission_rpc import Client
        from core.instance import get_instance
        from core.config import INSTANCE_ID
        inst = get_instance()
        host     = inst["transmission_host"]
        port     = inst["transmission_port"]
        user     = inst["transmission_user"]
        pwd      = inst["transmission_pass"]
        base_dir = inst["download_dir"]

        client = Client(host=host, port=port, username=user, password=pwd)
        download_dir = f"{base_dir.rstrip('/')}/{subdir}" if subdir and base_dir else base_dir or None

        magnet = item.get("magnet") or item.get("link") or ""
        has_getter = bool(item.get("_magnet_getter"))

        # Scraper items: link points to a detail page — resolve magnet lazily
        if not magnet.startswith("magnet:") and has_getter:
            magnet = item["_magnet_getter"]() or ""

        torrent_url = item.get("torrent_url") or ""

        kwargs = {}
        if download_dir:
            kwargs["download_dir"] = download_dir

        if magnet.startswith("magnet:"):
            t = client.add_torrent(magnet, **kwargs)
        elif torrent_url and torrent_url.endswith(".torrent"):
            t = client.add_torrent(torrent_url, **kwargs)
        else:
            return False

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
        return True
    except Exception:
        return False


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


import logging as _logging
_wl_log = _logging.getLogger("watchlist")


def run_watchlist_entry_now(entry_id: int) -> str:
    """
    Polls all relevant feeds for a specific watchlist entry.
    Pipeline: read RSS → term match → exclusions → global filters (with rejection log) → Transmission.
    Updates last_run_at, writes WatchlistLog. Returns a human-readable summary.
    """
    from datetime import datetime as _dt
    from core.db import Feed, Setting, WatchlistLog

    from core.rss_parser import fetch_feed
    from core.scrapers import get_scraper
    from core.filters import get_global_filters, apply_global_filters

    with Session() as s:
        entry = s.query(Watchlist).filter_by(id=entry_id).first()
        if not entry:
            return "Intrare negăsită"

        terms     = [t.lower() for t in (entry.terms or [])]
        excl      = [e.lower() for e in (entry.exclusions or [])]
        subdir    = entry.download_subdir
        name      = entry.name
        feed_ids  = list(entry.feed_ids or [])
        log_level = entry.log_level or "full"  # full | sent | summary

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

                # Excluderi
                blocked_by_excl = next((e for e in excl if _norm(e) in t_norm), None)
                if blocked_by_excl:
                    _wl_log.debug("[%s] exclus '%s': %s", name, blocked_by_excl, title)
                    if log_level in ("full", "verbose"):
                        log_entries.append({"title": title, "action": "excluded", "reason": f'excludere: "{blocked_by_excl}"'})
                    blocked += 1
                    continue

                # Potrivire termeni (OR)
                matched_term = next((t for t in terms if _norm(t) in t_norm), None)
                if not matched_term:
                    if log_level == "verbose":
                        log_entries.append({"title": title, "action": "nomatch", "reason": "fără potrivire"})
                    continue

                # Filtre globale
                passed, reason = apply_global_filters(item, global_filters)
                if not passed:
                    _wl_log.info("[%s] blocat (%s): %s", name, reason, title)
                    if log_level in ("full", "verbose"):
                        log_entries.append({"title": title, "action": "blocked", "reason": reason})
                    blocked += 1
                    continue

                ok = _send_to_transmission(item, subdir)
                if ok:
                    sent += 1
                    _mark_seen(feed["id"], guid, title)
                    _wl_log.info("[%s] ✓ trimis '%s': %s", name, matched_term, title)
                    if log_level in ("full", "sent", "verbose"):
                        log_entries.append({"title": title, "action": "sent", "reason": f'termen: "{matched_term}"'})
                else:
                    _wl_log.warning("[%s] eroare Transmission: %s", name, title)
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

    if sent > 0:
        return f"✓ {sent} torente noi trimise la Transmission"
    if checked == 0:
        return "Niciun feed activ disponibil"
    return f"Niciun rezultat nou ({checked} items verificate)"



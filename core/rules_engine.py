import re
from core.db import Session, Rule, Watchlist, SeenItem, Download
from core.filters import apply_global_filters, get_global_filters


def _matches_rule(title: str, rule: Rule) -> bool:
    """
    must_contain: ALL terms must appear in title (AND).
    must_not_contain: NONE of these terms may appear (AND NOT).
    Empty list = no constraint.
    """
    t = title.lower()
    for term in (rule.must_contain or []):
        if term.lower() not in t:
            return False
    for term in (rule.must_not_contain or []):
        if term.lower() in t:
            return False
    return True


def _build_merged_filters(rule: Rule, global_filters: dict) -> dict:
    merged = dict(global_filters)
    for field in ("size_min_mb", "size_max_gb", "seeders_min",
                  "quality_banned", "resolution_min", "languages", "title_blacklist"):
        val = getattr(rule, field, None)
        if val is not None:
            merged[field] = val
    return merged


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
        from core.db import Setting as S
        with Session() as s:
            def get(key, default):
                row = s.query(S).filter_by(key=key).first()
                return row.value if row else default
            host     = get("transmission_host", "localhost")
            port     = int(get("transmission_port", "9091"))
            user     = get("transmission_user", "")
            pwd      = get("transmission_pass", "")
            base_dir = get("transmission_download_dir", "")

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


def process_item(item: dict, feed_id: int) -> list[str]:
    """
    Runs a feed item through all active rules and watchlist entries.
    Returns a list of action strings for logging.
    """
    guid = item.get("guid") or item.get("link") or item.get("title", "")
    if _already_seen(guid):
        return []

    global_filters = get_global_filters()
    matched_any = False
    actions = []

    # ── Rules ────────────────────────────────────────────────────────────
    with Session() as s:
        rules = s.query(Rule).filter_by(is_active=True).all()

    for rule in rules:
        if rule.feed_ids and feed_id not in rule.feed_ids:
            continue
        if not _matches_rule(item.get("title", ""), rule):
            continue

        merged = _build_merged_filters(rule, global_filters)
        passed, reason = apply_global_filters(item, merged)
        if not passed:
            actions.append(f"[{rule.name}] blocat: {reason}")
            continue

        sent = _send_to_transmission(item, rule.download_subdir)
        if sent:
            matched_any = True
            actions.append(f"[{rule.name}] → Transmission ({rule.download_subdir or 'default'})")
        else:
            actions.append(f"[{rule.name}] eroare Transmission")

    # ── Watchlist ────────────────────────────────────────────────────────
    with Session() as s:
        wl_entries = s.query(Watchlist).filter_by(is_active=True).all()

    for entry in wl_entries:
        if entry.feed_ids and feed_id not in entry.feed_ids:
            continue

        matched_term = _matches_watchlist_term(item.get("title", ""), entry)
        if not matched_term:
            continue

        passed, _ = apply_global_filters(item, global_filters)
        if not passed:
            continue

        sent = _send_to_transmission(item, entry.download_subdir)
        if sent:
            matched_any = True
            actions.append(
                f"[WL:{entry.name}] \"{matched_term}\" → {entry.download_subdir or 'default'}"
            )
        else:
            actions.append(f"[WL:{entry.name}] eroare Transmission")

    if matched_any:
        _mark_seen(feed_id, guid, item.get("title", ""))

    return actions

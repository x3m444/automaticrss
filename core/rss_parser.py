import feedparser
import httpx


def validate_feed(url: str) -> tuple[bool, str]:
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        feed = feedparser.parse(resp.text)
        if feed.bozo and not feed.entries:
            return False, "URL-ul nu este un RSS valid"
        return True, f"{len(feed.entries)} items găsite"
    except Exception as e:
        return False, str(e)


def _torznab_attrs(entry) -> dict:
    """Extract torznab:attr name/value pairs into a flat dict."""
    attrs = {}
    for a in entry.get("torznab_attr", []):
        if isinstance(a, dict) and "name" in a and "value" in a:
            attrs[a["name"]] = a["value"]
    return attrs


def fetch_feed(url: str) -> list[dict]:
    resp = httpx.get(url, timeout=10, follow_redirects=True)
    feed = feedparser.parse(resp.text)
    items = []
    for entry in feed.entries:
        tz = _torznab_attrs(entry)

        guid = getattr(entry, "id", None) or entry.get("link", "")
        magnet = tz.get("magneturl") or (guid if guid.startswith("magnet:") else "")

        # size: standard <size> tag OR enclosure length
        size_bytes = 0
        raw_size = entry.get("size") or ""
        if raw_size:
            try:
                size_bytes = int(raw_size)
            except (ValueError, TypeError):
                pass
        if not size_bytes:
            for enc in entry.get("enclosures", []):
                try:
                    size_bytes = int(enc.get("length", 0) or 0)
                    if size_bytes:
                        break
                except (ValueError, TypeError):
                    pass

        # categories: Torznab puts multiple <category> as tags
        cats = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]

        items.append({
            "guid":       guid,
            "title":      entry.get("title", ""),
            "link":       entry.get("link", ""),
            "magnet":     magnet,
            "published":  entry.get("published", ""),
            "size_bytes": size_bytes,
            "size":       _fmt_size(size_bytes),
            "seeders":    int(tz.get("seeders", 0) or 0),
            "leechers":   int(tz.get("peers", 0) or 0),
            "infohash":   tz.get("infohash", ""),
            "category":   cats[0] if cats else "",
            "categories": cats,
        })
    return items


def _fmt_size(b: int) -> str:
    if not b:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"

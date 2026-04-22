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


def fetch_feed(url: str) -> list[dict]:
    resp = httpx.get(url, timeout=10, follow_redirects=True)
    feed = feedparser.parse(resp.text)
    items = []
    for entry in feed.entries:
        items.append({
            "guid": getattr(entry, "id", entry.get("link", "")),
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "size": entry.get("size", None),
            "category": entry.get("tags", [{}])[0].get("term", "") if entry.get("tags") else "",
        })
    return items

import httpx
import feedparser
from core.scrapers.base import BaseScraper, parse_size

_BASE = "https://xxxclub.to"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

_FEEDS = {
    "all":     "/feed/MG.xml",
    "480":     "/feed/480p.SD.xml",
    "720":     "/feed/720p.HD.xml",
    "1080":    "/feed/1080p.FullHD.xml",
    "dvd":     "/feed/Movies.DVD.WEB.xml",
    "4k":      "/feed/2160p.UHD.4K.xml",
    "imageset":"/feed/IMAGESET.xml",
    "vr":      "/feed/VR.VirtualReality.xml",
    "pack":    "/feed/Pack.MegaPack.xml",
}


def _fetch_rss(feed_path: str) -> list[dict]:
    r = httpx.get(f"{_BASE}{feed_path}", headers=_HEADERS, timeout=15, follow_redirects=True)
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    items = []
    for e in feed.entries:
        magnet = e.get("link", "")
        if not magnet.startswith("magnet:"):
            continue
        items.append({
            "title":   e.get("title", ""),
            "guid":    e.get("id") or e.get("link", ""),
            "magnet":  magnet,
            "url":     magnet,
            "link":    magnet,
            "seeders": 0,
            "size":    "",
            "size_bytes": 0,
        })
    return items


class XXXClub(BaseScraper):
    id = "xxxclub"
    name = "XXXClub"
    description = "XXXClub.to — tracker adult cu RSS direct, fără Cloudflare"
    base_url = _BASE

    categories = {
        "all":      "Toate categoriile",
        "480":      "480p/SD",
        "720":      "720p/HD",
        "1080":     "1080p/FullHD",
        "dvd":      "Movies/DVD/WEB",
        "4k":       "2160p/UHD/4K",
        "imageset": "IMAGESET",
        "vr":       "VR/VirtualReality",
        "pack":     "Pack/MegaPack",
    }

    def fetch_latest(self, categories: list[str] | None = None,
                     flaresolverr_url: str | None = None) -> list[dict]:
        cats = categories or ["all"]
        seen: set[str] = set()
        items: list[dict] = []
        for cat in cats:
            feed_path = _FEEDS.get(cat, _FEEDS["all"])
            try:
                for item in _fetch_rss(feed_path):
                    if item["guid"] not in seen:
                        seen.add(item["guid"])
                        item["source"] = self.name
                        items.append(item)
            except Exception:
                pass
        return items

    def search(self, query: str, flaresolverr_url: str | None = None) -> list[dict]:
        # Search by filtering RSS (limited to last 50 items per feed)
        try:
            words = [w.lower() for w in query.split() if len(w) > 2]
            if not words:
                return []
            items = _fetch_rss(_FEEDS["all"])
            results = []
            for item in items:
                title_lower = item["title"].lower()
                if all(w in title_lower for w in words):
                    item["source"] = self.name
                    results.append(item)
            return results
        except Exception:
            return []

    def get_magnet(self, detail_url: str, flaresolverr_url: str | None = None) -> str | None:
        # magnet is already in the url field
        if detail_url.startswith("magnet:"):
            return detail_url
        return None

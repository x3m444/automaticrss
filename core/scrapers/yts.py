import httpx
from urllib.parse import quote
from core.scrapers.base import BaseScraper, fmt_size

_API = "https://yts.mx/api/v2/list_movies.json"
_TRACKERS = (
    "udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce"
    "&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
    "&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce"
)

# Numeric codes → YTS quality param
_QUALITY_MAP: dict[str, str] = {
    "2000":   "All",
    "2040":   "1080p",
    "2045":   "2160p",
    "2060":   "3D",
    "100044": "1080p",
    "100045": "720p",
    "100046": "2160p",
    "100047": "3D",
}

# Genre names accepted directly by YTS API
_GENRES = {
    "action", "adventure", "animation", "biography", "comedy", "crime",
    "documentary", "drama", "family", "fantasy", "history", "horror",
    "music", "mystery", "romance", "sci-fi", "sport", "thriller",
    "war", "western",
}


def _resolve(cat: str) -> dict:
    """Returns dict with 'quality' and/or 'genre' API params for a given code."""
    if cat in _QUALITY_MAP:
        q = _QUALITY_MAP[cat]
        return {"quality": q} if q != "All" else {}
    if cat.lower() in _GENRES:
        return {"genre": cat.lower()}
    # passthrough — try as quality string (e.g. user typed "720p")
    return {"quality": cat}


class YTS(BaseScraper):
    id = "yts"
    name = "YTS"
    description = "Filme HD — yts.mx JSON API, fără scraping"
    base_url = "https://yts.mx"

    categories = {
        # Calitate (coduri Jackett)
        "2000":   "Movies (toate calitățile)",
        "2040":   "Movies/HD (1080p)",
        "2045":   "Movies/UHD (2160p)",
        "2060":   "Movies/3D",
        "100044": "Movies/x264/1080p",
        "100045": "Movies/x264/720p",
        "100046": "Movies/x264/2160p",
        "100047": "Movies/x264/3D",
        # Gen — se poate combina cu calitate via câmpul custom
        "action":       "Acțiune",
        "adventure":    "Aventură",
        "animation":    "Animație",
        "comedy":       "Comedie",
        "crime":        "Crimă",
        "documentary":  "Documentare",
        "drama":        "Dramă",
        "fantasy":      "Fantasy",
        "horror":       "Horror",
        "mystery":      "Mister",
        "romance":      "Romantice",
        "sci-fi":       "Sci-Fi",
        "thriller":     "Thriller",
        "western":      "Western",
    }

    def fetch_latest(
        self,
        categories: list[str] | None = None,
        flaresolverr_url: str | None = None,
    ) -> list[dict]:
        cats = categories if categories else [None]
        seen: set[str] = set()
        items: list[dict] = []

        for cat in cats:
            try:
                params: dict = {"sort_by": "date_added", "order_by": "desc", "limit": 50}
                if cat:
                    params.update(_resolve(cat))

                r = httpx.get(_API, params=params, timeout=15)
                r.raise_for_status()
                movies = r.json().get("data", {}).get("movies") or []

                for movie in movies:
                    for torrent in movie.get("torrents") or []:
                        ih = (torrent.get("hash") or "").lower()
                        if not ih or ih in seen:
                            continue
                        seen.add(ih)
                        quality = torrent.get("quality", "")
                        title = (
                            f"{movie.get('title', '?')} "
                            f"({movie.get('year', '')}) "
                            f"[{quality}]"
                        )
                        magnet = (
                            f"magnet:?xt=urn:btih:{ih}"
                            f"&dn={quote(title)}"
                            f"&tr={_TRACKERS}"
                        )
                        size_b = torrent.get("size_bytes") or 0
                        items.append({
                            "title":      title,
                            "guid":       ih,
                            "magnet":     magnet,
                            "size":       torrent.get("size") or fmt_size(size_b),
                            "size_bytes": size_b,
                            "seeders":    torrent.get("seeds") or 0,
                            "leechers":   torrent.get("peers") or 0,
                            "category":   cat or "movies",
                        })
            except Exception:
                pass

        return items

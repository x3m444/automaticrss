from bs4 import BeautifulSoup
from core.scrapers.base import BaseScraper, http_get, parse_int

_BASE = "https://therarbg.to"

# Newznab numeric codes → therarbg.to category name used in URL
_CAT_MAP: dict[str, str] = {
    "2000": "Movies",
    "3000": "Music",
    "4000": "Apps",
    "4050": "Games",
    "5000": "TV",
    "5070": "Anime",
    "6000": "XXX",
    "7000": "Books",
    "8000": "Other",
}

# Named categories accepted directly in the URL
_NAMED = {"Movies", "TV", "Games", "Music", "Anime", "Apps", "Other", "Books", "XXX"}


def _resolve(cat: str) -> str:
    """Map numeric Newznab code or passthrough named category."""
    if cat in _CAT_MAP:
        return _CAT_MAP[cat]
    if cat in _NAMED:
        return cat
    # try parent category (e.g. 5070 → TV/Anime → fallback to TV)
    for prefix, name in _CAT_MAP.items():
        if cat.startswith(prefix[:2]):
            return name
    return "Movies"


class TheRARBG(BaseScraper):
    id = "therarbg"
    name = "TheRARBG"
    description = "Clone RARBG — scraping HTML, poate necesita FlareSolverr"
    base_url = _BASE

    categories = {
        "2000": "Movies",
        "3000": "Music",
        "4000": "Apps",
        "4050": "Games",
        "5000": "TV",
        "5070": "Anime",
        "6000": "XXX",
        "7000": "Books",
        "8000": "Other",
    }

    def search(self, query: str, flaresolverr_url: str | None = None) -> list[dict]:
        try:
            from urllib.parse import quote
            html = http_get(
                f"{_BASE}/get-posts/keywords:{quote(query, safe='')}:time:30D/",
                flaresolverr_url=flaresolverr_url,
            )
            items = _parse_html(html, "search")
            for i in items:
                i["source"] = self.name
            return items
        except Exception:
            return []

    def fetch_latest(
        self,
        categories: list[str] | None = None,
        flaresolverr_url: str | None = None,
    ) -> list[dict]:
        # resolve & deduplicate category names
        seen_cats: set[str] = set()
        url_cats: list[str] = []
        for cat in (categories or ["Movies"]):
            name = _resolve(cat)
            if name not in seen_cats:
                seen_cats.add(name)
                url_cats.append(name)

        items: list[dict] = []
        seen_guids: set[str] = set()

        for cat_name in url_cats:
            try:
                html = http_get(
                    f"{_BASE}/get-posts/category:{cat_name}:time:10D/",
                    flaresolverr_url=flaresolverr_url,
                )
                for item in _parse_html(html, cat_name):
                    if item["guid"] not in seen_guids:
                        seen_guids.add(item["guid"])
                        items.append(item)
            except Exception:
                pass

        return items

    def get_magnet(self, detail_url: str, flaresolverr_url: str | None = None) -> str | None:
        try:
            html = http_get(detail_url, flaresolverr_url=flaresolverr_url)
            soup = BeautifulSoup(html, "html.parser")
            a = soup.select_one('a[href^="magnet:"]')
            return a["href"] if a else None
        except Exception:
            return None


def _parse_html(html: str, cat: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for row in soup.select("tr.list-entry"):
        a = row.select_one("td.cellName a")
        if not a:
            continue
        title = a.get_text(strip=True)
        href  = a.get("href", "")
        if not href or not title:
            continue
        detail_url = href if href.startswith("http") else _BASE + href

        size_td = row.select_one("td.sizeCell")
        size = size_td.get_text(strip=True).replace("\xa0", " ") if size_td else ""

        tds = row.find_all("td")
        seeders  = parse_int(tds[-2].get_text(strip=True)) if len(tds) >= 2 else 0
        leechers = parse_int(tds[-1].get_text(strip=True)) if len(tds) >= 1 else 0

        items.append({
            "title":    title,
            "guid":     detail_url,
            "url":      detail_url,
            "link":     detail_url,
            "size":     size,
            "seeders":  seeders,
            "leechers": leechers,
            "category": cat,
        })

    return items

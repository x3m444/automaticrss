from bs4 import BeautifulSoup
from core.scrapers.base import BaseScraper, http_get, parse_size, parse_int

BASE = "https://myporn.club"


class MyPornClub(BaseScraper):
    id = "mypornclub"
    name = "MyPornClub"
    description = "Public tracker for XXX content"
    base_url = BASE

    categories: dict[str, str] = {}  # single category site

    def fetch_latest(self, categories: list[str] | None = None, flaresolverr_url: str | None = None) -> list[dict]:
        html = http_get(f"{BASE}/ts", flaresolverr_url=flaresolverr_url)
        return _parse_listing(html)

    def search(self, query: str, categories: list[str] | None = None, flaresolverr_url: str | None = None) -> list[dict]:
        slug = query.strip().replace(" ", "-")
        html = http_get(f"{BASE}/s/{slug}", flaresolverr_url=flaresolverr_url)
        items = _parse_listing(html)
        for i in items:
            i["source"] = self.name
        return items

    def get_magnet(self, detail_url: str, flaresolverr_url: str | None = None) -> str | None:
        html = http_get(detail_url, flaresolverr_url=flaresolverr_url)
        soup = BeautifulSoup(html, "html.parser")
        a = soup.select_one('a[href^="magnet:?xt="]')
        return a["href"] if a else None


def _parse_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for el in soup.select("div.torrents_list > div.torrent_element"):
        a = el.select_one('a[href^="/t/"]')
        if not a:
            continue

        for tag in a.find_all("i"):
            tag.decompose()
        title = a.get_text(strip=True)
        if not title:
            continue

        detail_url = BASE + a.get("href", "")

        # span:nth-child(N) → 0-based index N-1
        spans = el.select("div.torrent_element_info span")
        size_str  = spans[3].get_text(strip=True)  if len(spans) > 3  else ""
        seeders   = parse_int(spans[9].get_text(strip=True)  if len(spans) > 9  else "")
        leechers  = parse_int(spans[11].get_text(strip=True) if len(spans) > 11 else "")

        items.append({
            "title":      title,
            "guid":       detail_url,
            "url":        detail_url,   # detail page; magnet fetched on rule match
            "link":       detail_url,
            "category":   "XXX",
            "size":       size_str,
            "size_bytes": parse_size(size_str),
            "seeders":    seeders,
            "leechers":   leechers,
        })

    return items

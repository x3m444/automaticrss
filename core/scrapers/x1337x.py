from bs4 import BeautifulSoup
from core.scrapers.base import BaseScraper, http_get, parse_int

_BASE = "https://1337x.to"

# Jackett/Newznab numeric codes → 1337x URL category segment
_CAT_MAP: dict[str, str] = {
    # Movies
    "2000": "Movies", "2010": "Movies", "2030": "Movies", "2040": "Movies",
    "2045": "Movies", "2060": "Movies", "2070": "Movies",
    "100001": "Movies", "100002": "Movies", "100003": "Movies", "100004": "Movies",
    "100042": "Movies", "100054": "Movies", "100055": "Movies", "100066": "Movies",
    "100070": "Movies", "100073": "Movies", "100076": "Movies",
    # TV
    "5000": "TV", "5030": "TV", "5040": "TV", "5080": "TV",
    "100005": "TV", "100006": "TV", "100007": "TV", "100009": "TV",
    "100041": "TV", "100071": "TV", "100074": "TV", "100075": "TV",
    # Anime
    "5070": "Anime",
    "100028": "Anime", "100078": "Anime", "100079": "Anime",
    "100080": "Anime", "100081": "Anime",
    # Music
    "3000": "Music", "3010": "Music", "3020": "Music",
    "3030": "Music", "3040": "Music", "3050": "Music",
    "100022": "Music", "100023": "Music", "100024": "Music", "100025": "Music",
    "100026": "Music", "100027": "Music", "100053": "Music", "100058": "Music",
    "100059": "Music", "100060": "Music", "100068": "Music", "100069": "Music",
    # Apps
    "4000": "Apps", "4030": "Apps", "4040": "Apps", "4060": "Apps", "4070": "Apps",
    "100018": "Apps", "100019": "Apps", "100020": "Apps",
    "100021": "Apps", "100056": "Apps", "100057": "Apps",
    # Games
    "4050": "Games",
    "1000": "Games", "1010": "Games", "1020": "Games", "1030": "Games",
    "1040": "Games", "1050": "Games", "1080": "Games", "1090": "Games",
    "1110": "Games", "1180": "Games",
    "100010": "Games", "100011": "Games", "100012": "Games", "100013": "Games",
    "100014": "Games", "100015": "Games", "100016": "Games", "100017": "Games",
    "100043": "Games", "100044": "Games", "100045": "Games", "100046": "Games",
    "100072": "Games", "100077": "Games", "100082": "Games",
    # XXX
    "6000": "XXX", "6010": "XXX", "6060": "XXX",
    "100048": "XXX", "100049": "XXX", "100050": "XXX", "100051": "XXX", "100067": "XXX",
    # Documentaries / Books
    "7000": "Documentaries", "7020": "Documentaries", "7030": "Documentaries",
    "100036": "Documentaries", "100039": "Documentaries", "100052": "Documentaries",
    # Other
    "8000": "Other", "8010": "Other",
    "100033": "Other", "100034": "Other", "100035": "Other",
    "100037": "Other", "100038": "Other", "100040": "Other", "100047": "Other",
}

def _resolve_cat(cat: str) -> str:
    """Numeric Jackett code → 1337x URL segment, or passthrough if already a name."""
    return _CAT_MAP.get(cat, cat)


class X1337x(BaseScraper):
    id = "1337x"
    name = "1337x"
    description = "Tracker public — scraping HTML, poate necesita FlareSolverr"
    base_url = _BASE

    categories = {
        # Console
        "1000":   "Console",
        "1010":   "Console/NDS",
        "1020":   "Console/PSP",
        "1030":   "Console/Wii",
        "1040":   "Console/XBox",
        "1050":   "Console/XBox 360",
        "1080":   "Console/PS3",
        "1090":   "Console/Other",
        "1110":   "Console/3DS",
        "1180":   "Console/PS4",
        # Movies
        "2000":   "Movies",
        "2010":   "Movies/Foreign",
        "2030":   "Movies/SD",
        "2040":   "Movies/HD",
        "2045":   "Movies/UHD",
        "2060":   "Movies/3D",
        "2070":   "Movies/DVD",
        "100001": "Movies/DVD",
        "100002": "Movies/Divx/Xvid",
        "100004": "Movies/Dubs/Dual Audio",
        "100042": "Movies/HD",
        "100054": "Movies/h.264/x264",
        "100055": "Movies/Mp4",
        "100066": "Movies/3D",
        "100070": "Movies/HEVC/x265",
        "100073": "Movies/Bollywood",
        "100076": "Movies/UHD",
        # Audio
        "3000":   "Audio",
        "3010":   "Audio/MP3",
        "3020":   "Audio/Video",
        "3030":   "Audio/Audiobook",
        "3040":   "Audio/Lossless",
        "3050":   "Audio/Other",
        "100022": "Music/MP3",
        "100023": "Music/Lossless",
        "100024": "Music/DVD",
        "100025": "Music/Video",
        "100026": "Music/Radio",
        "100027": "Music/Other",
        "100053": "Music/Album",
        "100058": "Music/Box set",
        "100059": "Music/Discography",
        "100060": "Music/Single",
        "100068": "Music/Concerts",
        "100069": "Music/AAC",
        # PC / Apps
        "4000":   "PC",
        "4030":   "PC/Mac",
        "4040":   "PC/Mobile-Other",
        "4050":   "PC/Games",
        "4060":   "PC/Mobile-iOS",
        "4070":   "PC/Mobile-Android",
        "100018": "Apps/PC Software",
        "100019": "Apps/Mac",
        "100020": "Apps/Linux",
        "100021": "Apps/Other",
        "100056": "Apps/Android",
        "100057": "Apps/iOS",
        # Games
        "100010": "Games/PC Game",
        "100011": "Games/PS2",
        "100012": "Games/PSP",
        "100013": "Games/Xbox",
        "100014": "Games/Xbox360",
        "100015": "Games/PS1",
        "100016": "Games/Dreamcast",
        "100017": "Games/Other",
        "100043": "Games/PS3",
        "100044": "Games/Wii",
        "100045": "Games/DS",
        "100046": "Games/GameCube",
        "100072": "Games/3DS",
        "100077": "Games/PS4",
        "100082": "Games/Switch",
        # TV
        "5000":   "TV",
        "5030":   "TV/SD",
        "5040":   "TV/HD",
        "5070":   "TV/Anime",
        "5080":   "TV/Documentary",
        "100005": "TV/DVD",
        "100006": "TV/Divx/Xvid",
        "100007": "TV/SVCD/VCD",
        "100009": "TV/Documentary",
        "100041": "TV/HD",
        "100067": "TV/HEVC/x265",  # typo in source kept as-is
        "100071": "TV/HEVC/x265",
        "100074": "TV/Cartoons",
        "100075": "TV/SD",
        # Anime
        "100028": "Anime/Anime",
        "100078": "Anime/Dual Audio",
        "100079": "Anime/Dubbed",
        "100080": "Anime/Subbed",
        "100081": "Anime/Raw",
        # XXX
        "6000":   "XXX",
        "6010":   "XXX/DVD",
        "6060":   "XXX/ImageSet",
        "100048": "XXX/Video",
        "100049": "XXX/Picture",
        "100050": "XXX/Magazine",
        "100051": "XXX/Hentai",
        "100067": "XXX/Games",
        # Books
        "7000":   "Books",
        "7020":   "Books/EBook",
        "7030":   "Books/Comics",
        "100036": "Other/E-books",
        "100039": "Other/Comics",
        "100052": "Other/Audiobook",
        # Other
        "8000":   "Other",
        "8010":   "Other/Misc",
        "100033": "Other/Emulation",
        "100034": "Other/Tutorial",
        "100035": "Other/Sounds",
        "100037": "Other/Images",
        "100038": "Other/Mobile Phone",
        "100040": "Other/Other",
        "100047": "Other/Nulled Script",
    }

    def search(self, query: str, flaresolverr_url: str | None = None) -> list[dict]:
        try:
            from urllib.parse import quote
            html = http_get(
                f"{_BASE}/search/{quote(query, safe='')}/1/",
                flaresolverr_url=flaresolverr_url,
            )
            items = _parse_listing(html)
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
        # resolve numeric codes → URL segment names, deduplicate pages
        url_cats: list[str] = []
        seen_cats: set[str] = set()
        for cat in (categories or ["Movies"]):
            resolved = _resolve_cat(cat)
            if resolved not in seen_cats:
                seen_cats.add(resolved)
                url_cats.append(resolved)

        items: list[dict] = []
        seen_guids: set[str] = set()

        for cat in url_cats:
            try:
                html = http_get(
                    f"{_BASE}/cat/{cat}/1/",
                    flaresolverr_url=flaresolverr_url,
                )
                for item in _parse_listing(html):
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


def _parse_listing(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    for row in soup.select("table.table-list tbody tr"):
        name_a = row.select_one("td.name a:last-child")
        if not name_a:
            continue
        title = name_a.get_text(strip=True)
        href  = name_a.get("href", "")
        if not href:
            continue
        detail_url = _BASE + href

        seeds   = parse_int(_text(row, "td.seeds"))
        leeches = parse_int(_text(row, "td.leeches"))
        size    = _text(row, "td.size")
        # size cell contains a <span> with unit — strip it
        size_tag = row.select_one("td.size")
        if size_tag:
            for span in size_tag.find_all("span"):
                span.decompose()
            size = size_tag.get_text(strip=True)

        items.append({
            "title":    title,
            "guid":     detail_url,
            "url":      detail_url,
            "link":     detail_url,
            "size":     size,
            "seeders":  seeds,
            "leechers": leeches,
        })

    return items


def _text(tag, selector: str) -> str:
    el = tag.select_one(selector)
    return el.get_text(strip=True) if el else ""

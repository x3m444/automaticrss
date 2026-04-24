import httpx
from urllib.parse import quote
from core.scrapers.base import BaseScraper, parse_int, fmt_size

_API = "https://apibay.org"
_TRACKERS = (
    "udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
    "&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce"
    "&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce"
    "&tr=udp%3A%2F%2Ftracker.tiny-vps.com%3A6969%2Fannounce"
)
_HEADERS = {"User-Agent": "Mozilla/5.0"}


class ThePirateBay(BaseScraper):
    id = "thepiratebay"
    name = "The Pirate Bay"
    description = "Public tracker — apibay.org JSON API, fără scraping"
    base_url = "https://thepiratebay.org"

    categories = {
        # Video
        "100207": "HD - Movies",
        "100211": "UHD/4k - Movies",
        "100201": "Movies",
        "100202": "Movies DVDR",
        "100208": "HD - TV shows",
        "100212": "UHD/4k - TV shows",
        "100205": "TV Shows",
        "100209": "3D",
        "100210": "CAM/TS",
        "100203": "Music Videos",
        "100204": "Movie Clips",
        "100299": "Video Other",
        # Audio
        "100101": "Music",
        "100102": "Audio Books",
        "100104": "FLAC",
        "100103": "Sound Clips",
        "100199": "Audio Other",
        # Aplicații
        "100301": "Windows",
        "100302": "Mac",
        "100303": "UNIX",
        "100306": "Android",
        "100305": "IOS (iPad/iPhone)",
        "100304": "Handheld",
        "100399": "Other OS",
        # Jocuri
        "100401": "PC",
        "100402": "Mac",
        "100403": "PSx",
        "100404": "XBOX360",
        "100405": "Wii",
        "100406": "Handheld",
        "100407": "IOS (iPad/iPhone)",
        "100408": "Android",
        "100499": "Games Other",
        # XXX
        "100500": "Porn",
        "100501": "Movies",
        "100502": "Movies DVDR",
        "100506": "Movie Clips",
        "100507": "UHD/4k - Movies",
        "100599": "Porn other",
        # Cărți
        "100601": "E-books",
        "100602": "Comics",
        "100603": "Pictures",
        "100604": "Covers",
        "100605": "Physibles",
        "100699": "Other Other",
    }

    def fetch_latest(
        self,
        categories: list[str] | None = None,
        flaresolverr_url: str | None = None,
    ) -> list[dict]:
        cats = categories if categories else ["all"]
        seen: set[str] = set()
        items: list[dict] = []

        for cat in cats:
            try:
                api_cat = cat[3:] if (cat.startswith("100") and len(cat) == 6) else cat
                r = httpx.get(
                    f"{_API}/precompiled/data_top100_{api_cat}.json",
                    headers=_HEADERS,
                    timeout=15,
                )
                r.raise_for_status()
                data = r.json()
                if not isinstance(data, list):
                    continue
                for row in data:
                    ih = (row.get("info_hash") or "").lower()
                    if not ih or ih in seen:
                        continue
                    seen.add(ih)
                    name = row.get("name", "")
                    magnet = (
                        f"magnet:?xt=urn:btih:{ih}"
                        f"&dn={quote(name)}"
                        f"&tr={_TRACKERS}"
                    )
                    size_b = int(row.get("size", 0) or 0)
                    items.append({
                        "title":      name,
                        "guid":       ih,
                        "magnet":     magnet,
                        "size":       fmt_size(size_b),
                        "size_bytes": size_b,
                        "seeders":    parse_int(row.get("seeders", 0)),
                        "leechers":   parse_int(row.get("leechers", 0)),
                        "category":   str(row.get("category", "")),
                    })
            except Exception:
                pass

        return items

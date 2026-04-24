import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def http_get(url: str, flaresolverr_url: str | None = None, timeout: int = 20) -> str:
    if flaresolverr_url:
        r = httpx.post(
            f"{flaresolverr_url.rstrip('/')}/v1",
            json={"cmd": "request.get", "url": url, "maxTimeout": 60000},
            timeout=70,
        )
        r.raise_for_status()
        return r.json()["solution"]["response"]

    r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=timeout)
    r.raise_for_status()
    return r.text


def parse_size(s: str) -> int:
    """Converts '1.5 GB', '700 MB' etc. to bytes."""
    import re
    if not s:
        return 0
    s = s.strip().upper()
    m = re.search(r"([\d.,]+)\s*(GB|MB|KB|TB)?", s)
    if not m:
        return 0
    try:
        val = float(m.group(1).replace(",", "."))
        unit = m.group(2) or "MB"
        mult = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        return int(val * mult.get(unit, 1024**2))
    except Exception:
        return 0


def parse_int(s: str) -> int:
    try:
        return int(str(s).replace(",", "").replace(".", "").strip())
    except Exception:
        return 0


def fmt_size(n: int) -> str:
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class BaseScraper:
    id: str = ""
    name: str = ""
    description: str = ""
    base_url: str = ""
    categories: dict[str, str] = {}  # {id: "Display name"} — empty = no category filter

    def fetch_latest(
        self,
        categories: list[str] | None = None,
        flaresolverr_url: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    def get_magnet(self, detail_url: str, flaresolverr_url: str | None = None) -> str | None:
        return None

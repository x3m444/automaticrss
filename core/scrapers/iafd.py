from bs4 import BeautifulSoup

BASE = "https://www.iafd.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _get(url: str) -> str:
    from curl_cffi import requests as cffi_requests
    r = cffi_requests.get(url, impersonate="chrome", timeout=20)
    r.raise_for_status()
    return r.text


def search_performer(name: str) -> dict | None:
    """Search by name → returns basic info + IAFD URL for full details."""
    url = f"{BASE}/results.asp?searchtype=comprehensive&searchstring={name.replace(' ', '+')}"
    import httpx
    r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    performer = _parse_performer_from_search(soup)
    if not performer:
        return None

    return performer


def get_performer_details(iafd_url: str) -> dict:
    """Fetch full performer page (bypasses Cloudflare via curl-cffi).
    Returns {name, photo_url, bio: {}, movies: [{title, year, distributor, iafd_url}]}"""
    html = _get(iafd_url)
    soup = BeautifulSoup(html, "html.parser")

    name = ""
    h1 = soup.select_one("h1")
    if h1:
        name = h1.get_text(strip=True)

    photo_url = None
    img = soup.select_one('img[src*="headshots"]')
    if img:
        photo_url = img["src"]

    bio = _parse_bio(soup)
    movies = _parse_filmography(soup)

    return {
        "name":      name,
        "photo_url": photo_url,
        "iafd_url":  iafd_url,
        "bio":       bio,
        "movies":    movies,
    }


def _parse_performer_from_search(soup: BeautifulSoup) -> dict | None:
    for table_id in ("#tblFem", "#tblMal"):
        rows = soup.select(f"{table_id} tr")
        for row in rows:
            a = row.find("a", href=lambda h: h and "person.rme" in h)
            img = row.find("img")
            if a:
                href = a["href"]
                return {
                    "name":      a.get_text(strip=True),
                    "photo_url": img["src"] if img and img.get("src") else None,
                    "iafd_url":  BASE + href if href.startswith("/") else href,
                }
    return None


def _parse_bio(soup: BeautifulSoup) -> dict:
    bio = {}
    labels = {
        "ethnicity": "Ethnicity",
        "nationality": "Nationality",
        "hair": "Hair Colors",
        "eye_color": "Eye Color",
        "height": "Height",
        "weight": "Weight",
        "measurements": "Measurements",
    }
    paragraphs = soup.select("#home p")
    for i, p in enumerate(paragraphs):
        txt = p.get_text(strip=True)
        for key, label in labels.items():
            if txt == label and i + 1 < len(paragraphs):
                val = paragraphs[i + 1].get_text(strip=True)
                if val and val not in labels.values():
                    bio[key] = val
    return bio


def _parse_filmography(soup: BeautifulSoup) -> list[dict]:
    movies = []
    for row in soup.select("#personal tbody tr"):
        cols = row.select("td")
        if len(cols) < 2:
            continue
        a = cols[0].find("a")
        year = cols[1].get_text(strip=True)
        distributor = cols[2].get_text(strip=True) if len(cols) > 2 else ""
        if not a:
            continue
        href = a.get("href", "")
        movies.append({
            "title":       a.get_text(strip=True),
            "year":        year,
            "distributor": distributor,
            "iafd_url":    BASE + href if href.startswith("/") else href,
        })
    return sorted(movies, key=lambda m: m["year"], reverse=True)

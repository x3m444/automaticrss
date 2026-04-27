from bs4 import BeautifulSoup
from .base import http_get

BASE = "https://www.iafd.com"


def search_performer(name: str) -> dict | None:
    """Returns {name, photo_url, iafd_url, movies: [{title, year, iafd_url}]} or None."""
    url = f"{BASE}/results.asp?searchtype=comprehensive&searchstring={name.replace(' ', '+')}"
    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")

    performer = _parse_performer(soup)
    movies = _parse_movies(soup)

    if not performer and not movies:
        return None

    return {
        "name":      performer.get("name", name.title()) if performer else name.title(),
        "photo_url": performer.get("photo_url") if performer else None,
        "iafd_url":  performer.get("iafd_url") if performer else None,
        "movies":    movies,
    }


def _parse_performer(soup: BeautifulSoup) -> dict | None:
    for table_id in ("#tblFem", "#tblMal"):
        rows = soup.select(f"{table_id} tr")
        for row in rows:
            a = row.find("a", href=lambda h: h and "person.rme" in h)
            img = row.find("img")
            if a:
                name_text = a.get_text(strip=True) or ""
                return {
                    "name":      name_text,
                    "photo_url": img["src"] if img and img.get("src") else None,
                    "iafd_url":  BASE + a["href"] if a["href"].startswith("/") else a["href"],
                }
    return None


def _parse_movies(soup: BeautifulSoup) -> list[dict]:
    movies = []
    for row in soup.select("#titleresult tr")[1:]:
        cols = row.select("td")
        if not cols:
            continue
        a = cols[0].find("a") if cols else None
        year = cols[1].get_text(strip=True) if len(cols) > 1 else ""
        if not a:
            continue
        href = a["href"]
        movies.append({
            "title":    a.get_text(strip=True),
            "year":     year,
            "iafd_url": BASE + href if href.startswith("/") else href,
        })
    return movies

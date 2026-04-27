import httpx
from core.config import _load_secrets

BASE = "https://api.theporndb.net"


def _headers() -> dict:
    key = _load_secrets().get("TPDB_API_KEY", "")
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def search_performer(name: str) -> dict | None:
    r = httpx.get(f"{BASE}/performers", params={"q": name}, headers=_headers(), timeout=15)
    r.raise_for_status()
    results = r.json().get("data", [])
    if not results:
        return None
    p = results[0]
    extras = p.get("extras") or {}
    posters = p.get("posters") or []
    photo = posters[0]["url"] if posters else p.get("image")
    return {
        "name":      p.get("name", ""),
        "slug":      p.get("slug", ""),
        "photo_url": photo,
        "bio":       p.get("bio", ""),
        "rating":    p.get("rating"),
        "extras": {
            "birthday":     extras.get("birthday", ""),
            "birthplace":   extras.get("birthplace", ""),
            "nationality":  extras.get("nationality", ""),
            "ethnicity":    extras.get("ethnicity", ""),
            "height":       extras.get("height", ""),
            "weight":       extras.get("weight", ""),
            "measurements": extras.get("measurements", ""),
            "hair":         extras.get("hair_colour", ""),
            "eye_color":    extras.get("eye_colour", ""),
            "tattoos":      extras.get("tattoos", ""),
            "career_start": extras.get("career_start_year"),
            "career_end":   extras.get("career_end_year"),
        },
    }


def search_movies(query: str, page: int = 1, per_page: int = 24) -> dict:
    r = httpx.get(
        f"{BASE}/movies",
        params={"q": query, "page": page, "per_page": per_page},
        headers=_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return _parse_movies_response(r.json())


def get_latest_movies(page: int = 1, per_page: int = 48) -> dict:
    r = httpx.get(
        f"{BASE}/movies",
        params={"page": page, "per_page": per_page, "sort": "created_at", "order": "desc"},
        headers=_headers(),
        timeout=15,
    )
    r.raise_for_status()
    return _parse_movies_response(r.json())


def _parse_movies_response(data: dict) -> dict:
    movies = []
    for m in data.get("data", []):
        posters = m.get("posters") or {}
        poster = posters.get("medium") or posters.get("large") or m.get("poster") or m.get("image")
        tags = [t.get("name") for t in (m.get("tags") or [])[:6] if t.get("name")]
        movies.append({
            "title":  m.get("title", ""),
            "date":   m.get("date", ""),
            "year":   (m.get("date") or "")[:4],
            "poster": poster,
            "url":    m.get("url", ""),
            "tags":   tags,
            "rating": m.get("rating", 0),
        })
    meta = data.get("meta", {})
    return {
        "movies":       movies,
        "total":        meta.get("total", 0),
        "current_page": meta.get("current_page", 1),
        "last_page":    meta.get("last_page", 1),
    }


def get_movies(slug: str, page: int = 1, per_page: int = 24) -> dict:
    r = httpx.get(
        f"{BASE}/performers/{slug}/movies",
        params={"page": page, "per_page": per_page},
        headers=_headers(),
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    movies = []
    for m in data.get("data", []):
        posters = m.get("posters") or {}
        poster = posters.get("medium") or posters.get("large") or m.get("poster") or m.get("image")
        movies.append({
            "title":  m.get("title", ""),
            "date":   m.get("date", ""),
            "year":   (m.get("date") or "")[:4],
            "poster": poster,
            "url":    m.get("url", ""),
        })
    meta = data.get("meta", {})
    return {
        "movies":       movies,
        "total":        meta.get("total", 0),
        "current_page": meta.get("current_page", 1),
        "last_page":    meta.get("last_page", 1),
    }

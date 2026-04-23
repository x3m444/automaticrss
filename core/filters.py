import json
import re
from core.db import Session, Setting

FILTERS_KEY = "global_filters"
RESOLUTION_ORDER = {"orice": 0, "480p": 480, "720p": 720, "1080p": 1080, "4k": 2160}


def get_global_filters() -> dict:
    with Session() as s:
        row = s.query(Setting).filter_by(key=FILTERS_KEY).first()
        if row and row.value:
            return json.loads(row.value)
    return {}


def _resolution_value(title: str) -> int:
    title_lower = title.lower()
    if "4k" in title_lower or "2160p" in title_lower:
        return 2160
    if "1080p" in title_lower or "1080i" in title_lower:
        return 1080
    if "720p" in title_lower or "720i" in title_lower:
        return 720
    if "480p" in title_lower:
        return 480
    return 0


def apply_global_filters(item: dict, filters: dict | None = None) -> tuple[bool, str]:
    """
    Verifică dacă un item trece filtrele globale.
    Returnează (True, "") dacă trece sau (False, motiv) dacă e blocat.
    """
    if filters is None:
        filters = get_global_filters()

    if not filters:
        return True, ""

    title = item.get("title", "")
    size_bytes = item.get("size_bytes") or _parse_size(item.get("size", ""))
    seeders = int(item.get("seeders", 0) or 0)

    # Dimensiune minimă
    min_mb = filters.get("size_min_mb", 0)
    if min_mb and size_bytes and size_bytes < min_mb * 1024 * 1024:
        return False, f"Prea mic ({size_bytes // 1024 // 1024} MB < {min_mb} MB)"

    # Dimensiune maximă
    max_gb = filters.get("size_max_gb", 0)
    if max_gb and size_bytes and size_bytes > max_gb * 1024 * 1024 * 1024:
        return False, f"Prea mare ({size_bytes // 1024 // 1024 // 1024} GB > {max_gb} GB)"

    # Seederi minimi
    min_seed = filters.get("seeders_min", 0)
    if min_seed and seeders < min_seed:
        return False, f"Prea puțini seederi ({seeders} < {min_seed})"

    # Calități interzise
    title_upper = title.upper()
    for banned in filters.get("quality_banned", []):
        if re.search(rf"\b{re.escape(banned)}\b", title_upper):
            return False, f"Calitate interzisă: {banned}"

    # Rezoluție minimă
    res_min = filters.get("resolution_min", "Orice").lower()
    min_res_val = RESOLUTION_ORDER.get(res_min, 0)
    if min_res_val > 0:
        item_res = _resolution_value(title)
        if item_res > 0 and item_res < min_res_val:
            return False, f"Rezoluție insuficientă ({item_res}p < {min_res_val}p)"

    # Blacklist cuvinte titlu
    for word in filters.get("title_blacklist", []):
        if re.search(rf"\b{re.escape(word.upper())}\b", title_upper):
            return False, f"Cuvânt blocat în titlu: {word}"

    return True, ""


def _parse_size(size_str: str) -> int:
    """Convertește string de dimensiune (ex: '1.5 GB', '700 MB') în bytes."""
    if not size_str:
        return 0
    size_str = size_str.strip().upper()
    try:
        match = re.search(r"([\d.,]+)\s*(GB|MB|KB|TB)?", size_str)
        if not match:
            return 0
        val = float(match.group(1).replace(",", "."))
        unit = match.group(2) or "MB"
        multipliers = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
        return int(val * multipliers.get(unit, 1024**2))
    except Exception:
        return 0

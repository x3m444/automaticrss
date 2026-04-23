import zipfile
import io
import threading
from pathlib import Path
from datetime import datetime
import httpx
import yaml

INDEXERS_DIR = Path(__file__).parent.parent / "indexers"
JACKETT_ZIP_URL = "https://github.com/Jackett/Jackett/archive/refs/heads/master.zip"
DEFINITIONS_PREFIX = "Jackett-master/src/Jackett.Common/Definitions/"

# ── Cache global în memorie ─────────────────────────────────────────────────
_cache: list[dict] = []
_cache_lock = threading.Lock()
_last_sync: datetime | None = None


def get_indexers_cache() -> list[dict]:
    return _cache


def load_cache_from_disk():
    """Încarcă toți indexerii de pe disk în RAM la startup."""
    global _cache
    meta = []
    for path in sorted(INDEXERS_DIR.glob("*.yml")):
        m = _parse_meta(path.stem, path)
        if m:
            meta.append(m)
    with _cache_lock:
        _cache = meta


def _parse_meta(indexer_id: str, path: Path) -> dict | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cats = []
        if "caps" in data and "categorymappings" in data["caps"]:
            cats = sorted(set(
                m.get("cat", "") for m in data["caps"]["categorymappings"] if m.get("cat")
            ))
        return {
            "id": indexer_id,
            "name": data.get("name", indexer_id),
            "type": data.get("type", "unknown"),
            "language": data.get("language", ""),
            "description": data.get("description", ""),
            "categories": cats,
        }
    except Exception:
        return None


def sync_indexers() -> tuple[int, str]:
    """Descarcă toate definițiile Jackett și reîncarcă cache-ul."""
    global _last_sync
    try:
        resp = httpx.get(JACKETT_ZIP_URL, follow_redirects=True, timeout=60)
        resp.raise_for_status()

        INDEXERS_DIR.mkdir(exist_ok=True)
        count = 0
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            for name in z.namelist():
                if name.startswith(DEFINITIONS_PREFIX) and name.endswith(".yml"):
                    fname = Path(name).name
                    (INDEXERS_DIR / fname).write_bytes(z.read(name))
                    count += 1

        _last_sync = datetime.now()
        load_cache_from_disk()
        return count, f"{count} indexeri sincronizați"
    except Exception as e:
        return 0, f"Eroare: {e}"


def sync_indexers_background():
    """Rulează sync în background thread — folosit de scheduler."""
    threading.Thread(target=sync_indexers, daemon=True).start()


def list_indexers_meta() -> list[dict]:
    """Returnează cache-ul — instant, fără I/O."""
    return _cache


def load_indexer_meta(indexer_id: str) -> dict:
    for m in _cache:
        if m["id"] == indexer_id:
            return m
    return {}


def get_last_sync() -> datetime | None:
    return _last_sync

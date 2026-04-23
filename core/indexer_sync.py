import zipfile
import io
from pathlib import Path
import httpx
import yaml

INDEXERS_DIR = Path(__file__).parent.parent / "indexers"
JACKETT_ZIP_URL = "https://github.com/Jackett/Jackett/archive/refs/heads/master.zip"
DEFINITIONS_PREFIX = "Jackett-master/src/Jackett.Common/Definitions/"


def sync_indexers() -> tuple[int, str]:
    """Descarcă și extrage toate definițiile Jackett. Returnează (count, mesaj)."""
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

        return count, f"{count} indexeri sincronizați"
    except Exception as e:
        return 0, f"Eroare: {e}"


def load_indexer_meta(indexer_id: str) -> dict:
    """Citește metadata dintr-un YAML (name, type, language, categories)."""
    path = INDEXERS_DIR / f"{indexer_id}.yml"
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cats = []
        if "caps" in data and "categorymappings" in data["caps"]:
            cats = list({m.get("cat", "") for m in data["caps"]["categorymappings"] if m.get("cat")})
        return {
            "id": indexer_id,
            "name": data.get("name", indexer_id),
            "type": data.get("type", "unknown"),
            "language": data.get("language", ""),
            "description": data.get("description", ""),
            "categories": cats,
        }
    except Exception:
        return {"id": indexer_id, "name": indexer_id, "type": "unknown", "language": "", "description": "", "categories": []}


def list_indexers_meta() -> list[dict]:
    """Returnează metadata pentru toți indexerii disponibili."""
    results = []
    for path in sorted(INDEXERS_DIR.glob("*.yml")):
        meta = load_indexer_meta(path.stem)
        if meta:
            results.append(meta)
    return results

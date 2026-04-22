"""Motor Cardigann simplificat — executa definitii YAML compatibile Jackett."""
import re
import yaml
import httpx
from pathlib import Path
from bs4 import BeautifulSoup
from jinja2 import Environment

INDEXERS_DIR = Path(__file__).parent.parent / "indexers"


def load_indexer(indexer_id: str) -> dict:
    path = INDEXERS_DIR / f"{indexer_id}.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_indexers() -> list[str]:
    return [p.stem for p in INDEXERS_DIR.glob("*.yml")]


def _build_path(path_template: str, keywords: str) -> str:
    env = Environment()
    keywords_slug = re.sub(r"\s+", "-", keywords.strip())
    template = env.from_string(path_template.replace("re_replace", "replace"))
    return template.render(Keywords=keywords_slug)


def search(indexer_id: str, keywords: str = "") -> list[dict]:
    definition = load_indexer(indexer_id)
    base_url = definition["links"][0].rstrip("/")
    path_tpl = definition["search"]["paths"][0]["path"]
    path = _build_path(path_tpl, keywords)

    url = f"{base_url}/{path}"
    resp = httpx.get(url, timeout=15, follow_redirects=True)
    soup = BeautifulSoup(resp.text, "lxml")

    row_selector = definition["search"]["rows"]["selector"]
    fields = definition["search"]["fields"]
    download_selector = definition["download"]["selector"]
    download_attr = definition["download"]["attribute"]

    results = []
    for row in soup.select(row_selector):
        item = {}
        for field_name, field_def in fields.items():
            if "text" in field_def:
                item[field_name] = str(field_def["text"])
            elif "selector" in field_def:
                el = row.select_one(field_def["selector"])
                if el:
                    item[field_name] = el.get(field_def.get("attribute", ""), el.get_text(strip=True))
                else:
                    item[field_name] = ""

        dl_el = row.select_one(download_selector)
        item["magnet"] = dl_el.get(download_attr, "") if dl_el else ""
        results.append(item)

    return results

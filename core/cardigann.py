"""Motor Cardigann simplificat — executa definitii YAML compatibile Jackett."""
import re
import yaml
import httpx
from pathlib import Path
from bs4 import BeautifulSoup

INDEXERS_DIR = Path(__file__).parent.parent / "indexers"


def load_indexer(indexer_id: str) -> dict:
    path = INDEXERS_DIR / f"{indexer_id}.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def list_indexers() -> list[str]:
    return [p.stem for p in INDEXERS_DIR.glob("*.yml")]


def _build_search_path(path_template: str, keywords: str) -> str:
    """Construiește URL-ul de search din template simplu."""
    slug = re.sub(r"\s+", "-", keywords.strip())
    # {{ if .Keywords }}...{{ else }}...{{ end }}
    match = re.search(r"\{\{-?\s*if\s+\.Keywords\s*-?\}\}(.*?)\{\{-?\s*else\s*-?\}\}(.*?)\{\{-?\s*end\s*-?\}\}", path_template, re.DOTALL)
    if match:
        return match.group(1).strip().replace("{{ re_replace .Keywords \"\\s+\" \"-\" }}", slug).replace(".Keywords", slug) if slug else match.group(2).strip()
    return path_template.replace("{{ re_replace .Keywords \"\\s+\" \"-\" }}", slug)


def _eval_template(tmpl: str, result: dict) -> str:
    """Evaluează template-uri Cardigann/Go basic cu referințe la .Result.xxx și .Config.xxx."""
    if "{{" not in tmpl:
        return tmpl

    # {{ or (.Result.a) (.Result.b) }} — primul non-gol
    def replace_or(m):
        refs = re.findall(r"\.Result\.(\w+)", m.group(1))
        for r in refs:
            val = result.get(r, "")
            if val:
                return val
        return ""
    tmpl = re.sub(r"\{\{-?\s*or\s+((?:\s*\(\.Result\.\w+\)\s*)+)-?\}\}", replace_or, tmpl)

    # {{ if .Config.xxx }}...{{ else }}...{{ end }} — ia ramura else (no config)
    tmpl = re.sub(
        r"\{\{-?\s*if\s+\.Config\.\w+\s*-?\}\}.*?\{\{-?\s*else\s*-?\}\}(.*?)\{\{-?\s*end\s*-?\}\}",
        lambda m: m.group(1), tmpl, flags=re.DOTALL
    )

    # {{ if .Config.xxx }}...{{ end }} fără else — elimină tot blocul
    tmpl = re.sub(
        r"\{\{-?\s*if\s+\.Config\.\w+\s*-?\}\}.*?\{\{-?\s*end\s*-?\}\}",
        "", tmpl, flags=re.DOTALL
    )

    # {{ .Result.fieldname }}
    tmpl = re.sub(r"\{\{-?\s*\.Result\.(\w+)\s*-?\}\}", lambda m: result.get(m.group(1), ""), tmpl)

    # elimină orice tag {{ }} rămas
    tmpl = re.sub(r"\{\{.*?\}\}", "", tmpl)

    return tmpl.strip()


def _extract_field(row, field_def: dict, result: dict) -> str:
    if not isinstance(field_def, dict):
        return str(field_def)
    if "selector" in field_def:
        el = row.select_one(field_def["selector"])
        if el:
            attr = field_def.get("attribute", "")
            val = el.get(attr, el.get_text(strip=True)) if attr else el.get_text(strip=True)
        else:
            val = str(field_def.get("default", ""))
        return val
    if "text" in field_def:
        return _eval_template(str(field_def["text"]), result)
    return ""


def search(indexer_id: str, keywords: str = "") -> list[dict]:
    definition = load_indexer(indexer_id)
    base_url = definition["links"][0].rstrip("/")
    path_tpl = definition["search"]["paths"][0].get("path", "")
    path = _build_search_path(path_tpl, keywords).lstrip("/")

    url = f"{base_url}/{path}"
    resp = httpx.get(url, timeout=15, follow_redirects=True)
    soup = BeautifulSoup(resp.text, "lxml")

    row_selector = definition["search"]["rows"]["selector"]
    fields = definition["search"].get("fields", {})

    dl_section = definition.get("download", {})
    dl_selector = dl_section.get("selector", "")
    dl_attr = dl_section.get("attribute", "href")

    results = []
    for row in soup.select(row_selector):
        item: dict = {}

        # prima trecere: câmpuri cu selector CSS (nu depind de altele)
        for field_name, field_def in fields.items():
            if isinstance(field_def, dict) and "selector" in field_def:
                item[field_name] = _extract_field(row, field_def, item)

        # a doua trecere: câmpuri cu text/template (pot depinde de câmpuri deja extrase)
        for field_name, field_def in fields.items():
            if isinstance(field_def, dict) and "text" in field_def:
                item[field_name] = _extract_field(row, field_def, item)

        # magnet link
        if not item.get("magnet") and dl_selector:
            dl_el = row.select_one(dl_selector)
            item["magnet"] = dl_el.get(dl_attr, "") if dl_el else ""
        if not item.get("magnet"):
            item["magnet"] = item.get("download", "")

        results.append(item)

    return results

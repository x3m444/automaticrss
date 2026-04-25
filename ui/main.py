from pathlib import Path
from nicegui import ui, app
from fastapi import Response
from fastapi.responses import FileResponse
from ui.pages import feeds, downloads, settings, filters, watchlist, search


@ui.page("/")
def index():
    ui.navigate.to("/feeds")


@app.get("/media/{path:path}")
def serve_media(path: str):
    from core.instance import get_instance
    inst = get_instance()
    dl_dir = inst.get("download_dir", "")
    if not dl_dir:
        return Response(status_code=404)
    full_path = Path(dl_dir) / path
    if not full_path.exists() or not full_path.is_file():
        return Response(status_code=404)
    try:
        full_path.resolve().relative_to(Path(dl_dir).resolve())
    except ValueError:
        return Response(status_code=403)
    return FileResponse(full_path)


def start_ui():
    from core.instance import ensure_instance
    ensure_instance()
    ui.run(title="AutomaticRSS", port=8080, reload=False)

import os
import subprocess
import platform
from pathlib import Path
from nicegui import ui, run, app
from ui.layout import navbar
from core.db import Session, Setting, Instance
from core.config import INSTANCE_ID


VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m4v", ".webm", ".mpg", ".mpeg"}
SUBTITLE_EXTS = {".srt", ".ass", ".ssa", ".sub", ".vtt"}


def _get_dl_dir() -> str:
    with Session() as s:
        inst = s.query(Instance).filter_by(id=INSTANCE_ID).first()
        return inst.download_dir if inst and inst.download_dir else ""


def _fmt_size(n: int) -> str:
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _fetch_transmission() -> dict[str, dict]:
    """Returns {torrent_name: {id, status, percent, hash}} keyed by folder/file name."""
    try:
        from transmission_rpc import Client
        from core.instance import get_instance
        inst = get_instance()
        client = Client(
            host=inst["transmission_host"],
            port=inst["transmission_port"],
            username=inst["transmission_user"],
            password=inst["transmission_pass"],
        )
        result = {}
        for t in client.get_torrents():
            result[t.name] = {
                "id":      t.id,
                "status":  t.status or "unknown",
                "percent": round((t.percentDone or 0) * 100, 1),
                "hash":    t.hashString or "",
            }
        return result
    except Exception:
        return {}


def _delete_torrent(torrent_id: int, delete_data: bool = True):
    try:
        from transmission_rpc import Client
        from core.instance import get_instance
        inst = get_instance()
        client = Client(
            host=inst["transmission_host"],
            port=inst["transmission_port"],
            username=inst["transmission_user"],
            password=inst["transmission_pass"],
        )
        client.remove_torrent(torrent_id, delete_data=delete_data)
        return True
    except Exception:
        return False


def _delete_path(path: Path):
    import shutil
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.is_file():
        path.unlink(missing_ok=True)


def _open_with_system(filepath: str):
    try:
        if platform.system() == "Windows":
            os.startfile(filepath)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", filepath])
        else:
            subprocess.Popen(["xdg-open", filepath])
    except Exception:
        pass


def _media_url(filepath: str, dl_dir: str) -> str:
    rel = Path(filepath).relative_to(Path(dl_dir))
    return "/media/" + rel.as_posix()


def _show_player(title: str, url: str):
    with ui.dialog().props("maximized") as dlg:
        with ui.card().classes("w-full h-full bg-black flex flex-col items-center justify-center gap-4"):
            with ui.row().classes("w-full justify-between items-center px-4 pt-2"):
                ui.label(title).classes("text-white text-sm truncate max-w-2xl")
                ui.button(icon="close", on_click=dlg.close).props("flat dense round color=white")

            ui.html(f'<video id="arss-player" controls autoplay '
                    f'style="max-width:100%;max-height:80vh;outline:none;background:#000" '
                    f'src="{url}">Browserul tău nu suportă tag-ul video.</video>')

    dlg.open()
    ui.timer(0.4, lambda: ui.run_javascript("""
        (function() {
            var v = document.getElementById('arss-player');
            if (!v || v.__wheelBound) return;
            v.__wheelBound = true;
            v.addEventListener('wheel', function(e) {
                e.preventDefault();
                v.currentTime = Math.max(0, v.currentTime + (e.deltaY > 0 ? -5 : 5));
            }, { passive: false });
        })();
    """), once=True)


def _status_badge(info: dict | None):
    if not info:
        return
    status = info["status"]
    pct    = info["percent"]
    color  = {
        "downloading": "blue",
        "seeding":     "green",
        "stopped":     "grey",
        "checking":    "orange",
        "queued":      "purple",
    }.get(status, "grey")
    label = f"{status} {pct}%" if status == "downloading" else status
    ui.badge(label, color=color)


def _render_file(f: Path, dl_dir: str, indent: int = 0):
    ext = f.suffix.lower()
    is_video    = ext in VIDEO_EXTS
    is_subtitle = ext in SUBTITLE_EXTS
    size_str    = _fmt_size(f.stat().st_size)

    icon = "movie" if is_video else ("subtitles" if is_subtitle else "insert_drive_file")
    color = "primary" if is_video else ("purple" if is_subtitle else "grey")

    with ui.row().classes("w-full items-center gap-2 py-0.5").style(f"padding-left:{indent * 20}px"):
        ui.icon(icon, color=color).classes("text-base shrink-0")
        ui.label(f.name).classes("flex-1 text-sm truncate")
        ui.label(size_str).classes("text-xs text-gray-400 shrink-0 w-20 text-right")

        if is_video:
            url = _media_url(str(f), dl_dir)

            def play(u=url, n=f.name):
                _show_player(n, u)

            def open_sys(fp=str(f)):
                _open_with_system(fp)

            ui.button(icon="play_circle", on_click=play).props(
                "flat dense round color=primary"
            ).tooltip("Redă în browser")
            ui.button(icon="open_in_new", on_click=open_sys).props(
                "flat dense round color=grey"
            ).tooltip("Deschide cu player sistem")


def _render_dir(path: Path, dl_dir: str, indent: int = 0, transmission_info: dict | None = None):
    """Renders a directory as an expandable expansion panel."""
    size_str = _fmt_size(_dir_size(path))

    header_text = path.name

    with ui.expansion(header_text).classes("w-full").props("dense") as exp:
        # header slot — injectăm badge și size în label
        with exp.add_slot("header"):
            with ui.row().classes("w-full items-center gap-2 flex-1"):
                ui.icon("folder", color="yellow").classes("text-base shrink-0")
                ui.label(header_text).classes("flex-1 text-sm font-medium truncate")
                ui.label(size_str).classes("text-xs text-gray-400 shrink-0")
                if transmission_info:
                    _status_badge(transmission_info)

        # conținut
        children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for child in children:
            if child.is_dir():
                _render_dir(child, dl_dir, indent + 1)
            else:
                _render_file(child, dl_dir, indent + 1)


@ui.page("/downloads")
def downloads_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Downloads").classes("text-2xl font-bold")
            refresh_btn = ui.button(icon="refresh").props("flat round dense")
            status_lbl  = ui.label("").classes("text-xs text-gray-400")

        err_lbl   = ui.label("").classes("text-sm text-red-400")
        container = ui.column().classes("w-full gap-2")

        async def refresh():
            refresh_btn.props(add="loading")
            err_lbl.set_text("")

            dl_dir = await run.io_bound(_get_dl_dir)
            if not dl_dir or not Path(dl_dir).is_dir():
                err_lbl.set_text("Director de download neconfigurat sau inexistent. Verifică Settings.")
                refresh_btn.props(remove="loading")
                return

            torrents, top_items = await run.io_bound(_scan, dl_dir)

            container.clear()
            status_lbl.set_text(f"{len(top_items)} intrări  ·  {_fmt_size(sum(s for _, s, _ in top_items))}")

            if not top_items:
                with container:
                    ui.label("Niciun fișier descărcat.").classes("text-gray-400 text-sm")
                refresh_btn.props(remove="loading")
                return

            with container:
                for path, size, children in top_items:
                    t_info = torrents.get(path.name)

                    with ui.card().classes("w-full"):
                        # header card — numele, size, status Transmission, butoane
                        with ui.row().classes("w-full items-center gap-3 px-1"):
                            icon = "folder" if path.is_dir() else "movie"
                            ui.icon(icon, color="yellow" if path.is_dir() else "primary").classes("shrink-0")
                            ui.label(path.name).classes("flex-1 font-medium text-sm truncate")
                            ui.label(_fmt_size(size)).classes("text-xs text-gray-400 shrink-0")
                            if t_info:
                                _status_badge(t_info)

                            async def do_delete(p=path, ti=t_info):
                                def _del():
                                    if ti:
                                        _delete_torrent(ti["id"], delete_data=False)
                                    _delete_path(p)
                                await run.io_bound(_del)
                                ui.notify("Șters", type="warning")
                                await refresh()

                            ui.button(icon="delete", on_click=do_delete).props(
                                "flat dense round color=red"
                            ).tooltip("Șterge fișiere + elimină din Transmission")

                        ui.separator().classes("my-1")

                        # conținut: folder tree sau fișier direct
                        if path.is_dir():
                            children_sorted = sorted(
                                path.iterdir(),
                                key=lambda p: (p.is_file(), p.name.lower())
                            )
                            for child in children_sorted:
                                if child.is_dir():
                                    _render_dir(child, dl_dir)
                                else:
                                    _render_file(child, dl_dir)
                        else:
                            _render_file(path, dl_dir)

            refresh_btn.props(remove="loading")

        refresh_btn.on("click", refresh)
        ui.timer(0.1, refresh, once=True)


def _scan(dl_dir: str) -> tuple[dict, list]:
    """Pure I/O: scan filesystem + fetch Transmission. Returns (torrents_dict, top_items)."""
    torrents = _fetch_transmission()
    root = Path(dl_dir)
    top_items = []
    for p in sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if p.name.startswith("."):
            continue
        size = _dir_size(p) if p.is_dir() else p.stat().st_size
        top_items.append((p, size, []))
    return torrents, top_items

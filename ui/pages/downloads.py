import os
import subprocess
import platform
from pathlib import Path
from nicegui import ui, run, app
from ui.layout import navbar
from core.db import Session, Instance
from core.config import INSTANCE_ID
from core.utils import clean_title, get_cleanup_tokens


VIDEO_EXTS    = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m4v", ".webm", ".mpg", ".mpeg"}
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


def _fmt_speed(bps: int) -> str:
    if not bps:
        return ""
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1024:
            return f"{bps:.0f} {unit}"
        bps /= 1024
    return f"{bps:.1f} GB/s"


def _fmt_eta(seconds: int) -> str:
    if seconds < 0:
        return "∞"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h {(seconds % 3600) // 60}m"


def _dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _fetch_all_transmission() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    """Single Transmission call → (active_list, by_name, by_hash).
    active_list: torrents not yet complete.
    by_name/by_hash: all torrents for filesystem matching."""
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
        active  = []
        by_name = {}
        by_hash = {}
        for t in client.get_torrents():
            is_stalled  = t.is_stalled or False
            pct         = round((t.percent_done or 0) * 100, 1)
            total       = t.total_size or 0
            meta_pct    = getattr(t, "metadata_percent_complete", 1.0) or 0.0
            raw_status  = t.status or "unknown"
            status      = "stalled" if is_stalled else raw_status
            ih          = t.info_hash or ""
            eta_val     = t.eta
            eta_secs    = int(eta_val.total_seconds()) if hasattr(eta_val, "total_seconds") else (eta_val or -1)

            info = {
                "id":        t.id,
                "name":      t.name,
                "status":    status,
                "percent":   pct,
                "meta_pct":  round(meta_pct * 100, 0),
                "rate_down": t.rate_download or 0,
                "rate_up":   t.rate_upload or 0,
                "eta":       eta_secs,
                "total":     total,
                "hash":      ih,
            }
            by_name[t.name] = info
            if ih:
                by_hash[ih.lower()] = info

            if raw_status not in ("seeding", "stopped", "seed_pending"):
                active.append(info)

        return active, by_name, by_hash
    except Exception:
        return [], {}, {}


def _delete_torrent(torrent_id: int, delete_data: bool = True) -> bool:
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
    """Șterge fișierele unui torrent fără a atinge structura de foldere."""
    if path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        for f in path.rglob("*"):
            if f.is_file():
                f.unlink(missing_ok=True)


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
            ui.html(
                f'<video id="arss-player" controls autoplay '
                f'style="max-width:100%;max-height:80vh;outline:none;background:#000" '
                f'src="{url}">Browserul tău nu suportă tag-ul video.</video>'
            )
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
    color  = {
        "downloading": "blue",
        "seeding":     "green",
        "stopped":     "grey",
        "checking":    "orange",
        "queued":      "purple",
        "stalled":     "red",
    }.get(status, "grey")
    pct   = info.get("percent", 0)
    label = f"{status} {pct}%" if status == "downloading" else status
    ui.badge(label, color=color)


def _render_file(f: Path, dl_dir: str, indent: int = 0, extra_stop: list | None = None):
    ext         = f.suffix.lower()
    is_video    = ext in VIDEO_EXTS
    is_subtitle = ext in SUBTITLE_EXTS
    size_str    = _fmt_size(f.stat().st_size)
    icon        = "movie" if is_video else ("subtitles" if is_subtitle else "insert_drive_file")
    color       = "primary" if is_video else ("purple" if is_subtitle else "grey")
    stem_clean  = clean_title(f.stem, extra_stop) + f.suffix

    with ui.row().classes("w-full items-center gap-2 py-0.5").style(f"padding-left:{indent * 20}px"):
        ui.icon(icon, color=color).classes("text-base shrink-0")
        lbl = ui.label(stem_clean).classes("flex-1 text-sm truncate")
        if stem_clean != f.name:
            lbl.tooltip(f.name)
        ui.label(size_str).classes("text-xs text-gray-400 shrink-0 w-20 text-right")

        if is_video:
            url = _media_url(str(f), dl_dir)
            ui.button(icon="play_circle", on_click=lambda u=url, n=f.name: _show_player(n, u)).props(
                "flat dense round color=primary"
            ).tooltip("Redă în browser")
            ui.button(icon="open_in_new", on_click=lambda fp=str(f): _open_with_system(fp)).props(
                "flat dense round color=grey"
            ).tooltip("Deschide cu player sistem")


def _render_dir(path: Path, dl_dir: str, indent: int = 0, extra_stop: list | None = None):
    size_str   = _fmt_size(_dir_size(path))
    clean_name = clean_title(path.name, extra_stop)

    with ui.expansion(clean_name).classes("w-full").props("dense") as exp:
        with exp.add_slot("header"):
            with ui.row().classes("w-full items-center gap-2 flex-1"):
                ui.icon("folder", color="yellow").classes("text-base shrink-0")
                lbl = ui.label(clean_name).classes("flex-1 text-sm font-medium truncate")
                if clean_name != path.name:
                    lbl.tooltip(path.name)
                ui.label(size_str).classes("text-xs text-gray-400 shrink-0")

        children = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for child in children:
            if child.is_dir():
                _render_dir(child, dl_dir, indent + 1, extra_stop=extra_stop)
            else:
                _render_file(child, dl_dir, indent + 1, extra_stop=extra_stop)


def _render_active(active: list[dict], extra_stop: list, on_delete):
    """Render 'În curs' section — torrents from Transmission not yet complete."""
    if not active:
        ui.label("Niciun torrent în curs de descărcare.").classes("text-gray-400 text-sm italic")
        return

    STATUS_COLOR = {
        "downloading": "blue",
        "stalled":     "red",
        "checking":    "orange",
        "queued":      "purple",
    }
    STATUS_ICON = {
        "downloading": "download",
        "stalled":     "warning",
        "checking":    "loop",
        "queued":      "schedule",
    }

    for t in active:
        status     = t["status"]
        pct        = t["percent"]
        rate_down  = t["rate_down"]
        eta        = t["eta"]
        name_clean = clean_title(t["name"], extra_stop)
        color      = STATUS_COLOR.get(status, "grey")
        icon       = STATUS_ICON.get(status, "hourglass_empty")
        is_meta    = t["meta_pct"] < 100 and t["total"] == 0

        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-center gap-3 px-1 py-1"):
                ui.icon(icon, color=color).classes("shrink-0")

                with ui.column().classes("flex-1 gap-0.5 min-w-0"):
                    lbl = ui.label(name_clean).classes("text-sm font-medium truncate")
                    if name_clean != t["name"]:
                        lbl.tooltip(t["name"])

                    if is_meta:
                        ui.label(f"Se preiau metadate… {t['meta_pct']:.0f}%").classes("text-xs text-gray-400")
                    else:
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.linear_progress(value=pct / 100, color=color).classes("flex-1").props("rounded")
                            ui.label(f"{pct}%").classes("text-xs w-10 text-right shrink-0")

                        speed_str = _fmt_speed(rate_down)
                        eta_str   = _fmt_eta(eta) if eta and eta > 0 else ""
                        meta_parts = [p for p in [speed_str, f"ETA {eta_str}" if eta_str else ""] if p]
                        if meta_parts:
                            ui.label("  ·  ".join(meta_parts)).classes("text-xs text-gray-400")

                ui.badge(status, color=color).props("outline")

                async def do_del(tid=t["id"]):
                    ok = await run.io_bound(_delete_torrent, tid, True)
                    ui.notify("Șters" if ok else "Eroare la ștergere", type="warning" if ok else "negative")
                    await on_delete()

                ui.button(icon="delete", on_click=do_del).props(
                    "flat dense round color=red"
                ).tooltip("Oprește și șterge")


@ui.page("/downloads")
def downloads_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Downloads").classes("text-2xl font-bold")
            refresh_btn = ui.button(icon="refresh").props("flat round dense")
            status_lbl  = ui.label("").classes("text-xs text-gray-400")

        err_lbl          = ui.label("").classes("text-sm text-red-400")
        active_container = ui.column().classes("w-full gap-2")
        done_container   = ui.column().classes("w-full gap-2")

        async def refresh():
            refresh_btn.props(add="loading")
            err_lbl.set_text("")

            dl_dir = await run.io_bound(_get_dl_dir)
            if not dl_dir or not Path(dl_dir).is_dir():
                err_lbl.set_text("Director de download neconfigurat sau inexistent. Verifică Settings.")
                refresh_btn.props(remove="loading")
                return

            active, by_name, by_hash, top_items, extra_stop = await run.io_bound(_scan, dl_dir)

            # ── În curs ──────────────────────────────────────────────────
            active_container.clear()
            with active_container:
                label = f"În curs ({len(active)})" if active else "În curs"
                color = "orange" if any(t["status"] == "stalled" for t in active) else "grey"
                with ui.expansion(label, icon="downloading").classes("w-full").props(f"dense header-class='text-{color}-400'"):
                    _render_active(active, extra_stop, on_delete=refresh)

            # ── Completate ───────────────────────────────────────────────
            done_container.clear()
            total_size = sum(s for _, s, _, _ in top_items)
            status_lbl.set_text(f"{len(top_items)} completate  ·  {_fmt_size(total_size)}")

            with done_container:
                ui.label("Completate").classes("text-lg font-semibold text-gray-300")

                if not top_items:
                    ui.label("Niciun fișier descărcat.").classes("text-gray-400 text-sm italic")
                else:
                    for path, size, _, t_info in top_items:
                        clean_name = clean_title(path.name, extra_stop)

                        with ui.card().classes("w-full"):
                            with ui.row().classes("w-full items-center gap-3 px-1"):
                                ui.icon(
                                    "folder" if path.is_dir() else "movie",
                                    color="yellow" if path.is_dir() else "primary",
                                ).classes("shrink-0")
                                lbl = ui.label(clean_name).classes("flex-1 font-medium text-sm truncate")
                                if clean_name != path.name:
                                    lbl.tooltip(path.name)
                                ui.label(_fmt_size(size)).classes("text-xs text-gray-400 shrink-0")
                                if t_info:
                                    _status_badge(t_info)

                                async def do_delete(p=path, ti=t_info):
                                    def _del():
                                        if ti:
                                            ok = _delete_torrent(ti["id"], delete_data=True)
                                            if not ok:
                                                _delete_path(p)
                                        else:
                                            _delete_path(p)
                                    await run.io_bound(_del)
                                    ui.notify("Șters", type="warning")
                                    await refresh()

                                ui.button(icon="delete", on_click=do_delete).props(
                                    "flat dense round color=red"
                                ).tooltip("Șterge fișiere + elimină din Transmission")

                            ui.separator().classes("my-1")

                            if path.is_dir():
                                for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
                                    if child.is_dir():
                                        _render_dir(child, dl_dir, extra_stop=extra_stop)
                                    else:
                                        _render_file(child, dl_dir, extra_stop=extra_stop)
                            else:
                                _render_file(path, dl_dir, extra_stop=extra_stop)

            refresh_btn.props(remove="loading")

        refresh_btn.on("click", refresh)
        ui.timer(0.1, refresh, once=True)


def _scan(dl_dir: str) -> tuple[list, dict, dict, list, list]:
    """Pure I/O — single Transmission call + filesystem scan.
    Returns (active, by_name, by_hash, top_items, extra_stop)."""
    active, by_name, by_hash = _fetch_all_transmission()
    extra_stop = get_cleanup_tokens()

    # Hash index from DB for fallback matching
    db_hashes: dict[str, str] = {}
    try:
        from core.db import Session, Download
        with Session() as s:
            for r in s.query(Download).filter_by(instance_id=INSTANCE_ID).all():
                if r.torrent_hash:
                    db_hashes[r.torrent_hash.lower()] = r.title or ""
    except Exception:
        pass

    root      = Path(dl_dir)
    top_items = []
    for p in sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if p.name.startswith("."):
            continue
        size   = _dir_size(p) if p.is_dir() else p.stat().st_size
        t_info = by_name.get(p.name)
        if not t_info:
            for h, title in db_hashes.items():
                if title and title == p.name:
                    t_info = by_hash.get(h)
                    if t_info:
                        break
        top_items.append((p, size, [], t_info))

    return active, by_name, by_hash, top_items, extra_stop

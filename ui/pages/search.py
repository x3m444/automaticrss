import threading
from nicegui import ui, run
from ui.layout import navbar
from core.scrapers import SCRAPERS
from core.db import Session, Setting, Watchlist
from core.utils import clean_title, get_cleanup_tokens


def _get_base_dir() -> str:
    with Session() as s:
        row = s.query(Setting).filter_by(key="transmission_download_dir").first()
        return row.value if row and row.value else ""


def _get_flaresolverr() -> str | None:
    with Session() as s:
        row = s.query(Setting).filter_by(key="flaresolverr_url").first()
        return row.value if row and row.value else None


def _known_subdirs() -> list[str]:
    with Session() as s:
        rows = s.query(Watchlist).filter(Watchlist.download_subdir.isnot(None)).all()
        seen = []
        for r in rows:
            if r.download_subdir and r.download_subdir not in seen:
                seen.append(r.download_subdir)
        return seen


def _send_download_sync(item: dict, subdir: str | None) -> tuple[bool, str]:
    try:
        from transmission_rpc import Client
        with Session() as s:
            def get(key, default):
                row = s.query(Setting).filter_by(key=key).first()
                return row.value if row else default
            host     = get("transmission_host", "localhost")
            port     = int(get("transmission_port", "9091"))
            user     = get("transmission_user", "")
            pwd      = get("transmission_pass", "")
            base_dir = get("transmission_download_dir", "")

        client = Client(host=host, port=port, username=user, password=pwd)
        download_dir = f"{base_dir.rstrip('/')}/{subdir}" if subdir and base_dir else base_dir or None

        magnet = item.get("magnet") or item.get("link") or ""
        getter = item.get("_magnet_getter")
        if not magnet.startswith("magnet:") and getter:
            magnet = getter() or ""

        if not magnet.startswith("magnet:"):
            return False, "Niciun magnet disponibil"

        kwargs = {"download_dir": download_dir} if download_dir else {}
        t = client.add_torrent(magnet, **kwargs)

        from core.db import Download
        with Session() as s:
            if not s.query(Download).filter_by(torrent_hash=t.hashString).first():
                s.add(Download(
                    torrent_hash=t.hashString,
                    title=item.get("title", ""),
                    status="queued",
                    size_bytes=item.get("size_bytes"),
                ))
                s.commit()
        return True, download_dir or "director default"
    except Exception as e:
        return False, str(e)


def _search_all(query: str, selected_ids: list[str], flaresolverr: str | None) -> list[dict]:
    """Rulează în thread pool via run.io_bound — nu atinge UI."""
    lock = threading.Lock()
    found: list[dict] = []

    def search_one(sc_id: str):
        cls = SCRAPERS.get(sc_id)
        if not cls:
            return
        try:
            scraper = cls()
            items = scraper.search(query, flaresolverr_url=flaresolverr)
            for item in items:
                if not item.get("magnet") and item.get("url"):
                    item["_magnet_getter"] = lambda url=item["url"]: scraper.get_magnet(
                        url, flaresolverr_url=flaresolverr
                    )
            with lock:
                found.extend(items)
        except Exception:
            pass

    threads = [threading.Thread(target=search_one, args=(sc_id,), daemon=True) for sc_id in selected_ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return found


@ui.page("/search")
def search_page():
    navbar()

    state: dict = {"results": []}
    _cleanup_tokens = get_cleanup_tokens()

    with ui.column().classes("w-full p-6 gap-6"):
        ui.label("Caută").classes("text-xl font-bold")

        # ── Formular ──────────────────────────────────────────────────────
        with ui.card().classes("w-full"):
            with ui.row().classes("w-full items-end gap-4 flex-wrap"):
                query_input = ui.input(
                    placeholder="ex: The Matrix, Terminator...",
                ).classes("flex-1 min-w-64")

                scraper_checks: dict[str, ui.checkbox] = {}
                with ui.row().classes("flex-wrap gap-4 items-center"):
                    ui.label("Surse:").classes("text-sm text-gray-400")
                    for sc_id, cls in SCRAPERS.items():
                        scraper_checks[sc_id] = ui.checkbox(cls.name, value=True)

            with ui.row().classes("items-center gap-4 mt-2"):
                search_btn = ui.button("Caută", icon="search").props("color=primary")
                status_label = ui.label("").classes("text-sm text-gray-400")

        # ── Rezultate ─────────────────────────────────────────────────────
        results_container = ui.column().classes("w-full")

        def _show_download_dialog(item: dict):
            base_dir = _get_base_dir()
            subdirs = _known_subdirs()

            with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label("Descarcă în...").classes("text-lg font-bold")
                    ui.button(icon="close", on_click=dlg.close).props("flat dense round")

                ui.label(item.get("title", "")[:80]).classes("text-sm text-gray-400")
                ui.separator()

                if base_dir:
                    ui.label(f"Root: {base_dir}").classes("text-xs font-mono text-gray-500")

                subdir_input = ui.input(
                    placeholder="ex: movies/action  (gol = root)",
                ).classes("w-full")

                if subdirs:
                    ui.label("Sugestii:").classes("text-xs text-gray-400 mt-1")
                    with ui.row().classes("flex-wrap gap-2"):
                        for sd in subdirs:
                            ui.button(
                                sd,
                                on_click=lambda s=sd: subdir_input.set_value(s),
                            ).props("flat dense outline rounded").classes("text-xs")

                ui.separator()

                with ui.row().classes("justify-end gap-2 items-center"):
                    ui.button("Anulează", on_click=dlg.close).props("flat")

                    async def do_download():
                        try:
                            subdir = subdir_input.value.strip() or None
                            dl_btn.props(add="loading")
                            ok, msg = await run.io_bound(_send_download_sync, item, subdir)
                            dl_btn.props(remove="loading")
                            dlg.close()
                            if ok:
                                ui.notify(f"✓ Trimis → {msg}", type="positive", timeout=4000)
                            else:
                                ui.notify(f"Eroare: {msg}", type="negative", timeout=6000)
                        except Exception as ex:
                            try:
                                dl_btn.props(remove="loading")
                            except Exception:
                                pass
                            ui.notify(f"Eroare neașteptată: {ex}", type="negative", timeout=8000)

                    dl_btn = ui.button(
                        "Descarcă", icon="download",
                        on_click=do_download,
                    ).props("color=primary")

            dlg.open()

        def _render_results():
            results_container.clear()
            results = state["results"]
            if not results:
                return

            shown = sorted(results, key=lambda x: x.get("seeders", 0) or 0, reverse=True)[:50]

            with results_container:
                suffix = " (top 50 după seederi)" if len(results) > 50 else ""
                ui.label(f"{len(results)} rezultate{suffix}").classes("text-sm text-gray-400")

                with ui.element("div").classes("w-full border border-gray-700 rounded overflow-hidden mt-2"):
                    with ui.row().classes("w-full items-center px-3 py-2 bg-gray-800 text-xs font-bold text-gray-400 gap-2"):
                        ui.label("Sursă").classes("w-28 shrink-0")
                        ui.label("Titlu").classes("flex-1")
                        ui.label("Mărime").classes("w-24 shrink-0")
                        ui.label("↑ Seed").classes("w-14 shrink-0 text-right")
                        ui.label("↓ Leech").classes("w-16 shrink-0 text-right")
                        ui.label("").classes("w-10 shrink-0")

                    for r in shown:
                        seeds = r.get("seeders", 0) or 0
                        leech = r.get("leechers", 0) or 0
                        raw_title = r.get("title", "")
                        display   = clean_title(raw_title, _cleanup_tokens)
                        with ui.row().classes("w-full items-center px-3 py-2 border-t border-gray-700 gap-2"):
                            ui.badge(r.get("source", "—")).props("outline color=purple").classes("w-28 shrink-0")
                            ui.label(display).classes("flex-1 text-sm").style(
                                "white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:500px"
                            ).tooltip(raw_title)
                            ui.label(r.get("size", "—")).classes("w-24 shrink-0 text-xs text-gray-400")
                            ui.label(str(seeds)).classes("w-14 shrink-0 text-xs text-right").style(
                                f"color: {'#4caf50' if seeds > 0 else '#9e9e9e'}"
                            )
                            ui.label(str(leech)).classes("w-16 shrink-0 text-xs text-right text-gray-400")
                            ui.button(
                                icon="download",
                                on_click=lambda item=r: _show_download_dialog(item),
                            ).props("flat dense round color=primary").classes("w-10 shrink-0")

        async def do_search():
            query = query_input.value.strip()
            if not query:
                ui.notify("Introdu un termen de căutare", type="warning")
                return

            selected = [sc_id for sc_id, cb in scraper_checks.items() if cb.value]
            if not selected:
                ui.notify("Selectează cel puțin o sursă", type="warning")
                return

            state["results"] = []
            results_container.clear()
            search_btn.props("loading")
            status_label.set_text(f"Se caută pe {len(selected)} surse...")

            flaresolverr = _get_flaresolverr()
            results = await run.io_bound(_search_all, query, selected, flaresolverr)

            state["results"] = results
            search_btn.props(remove="loading")
            status_label.set_text(f"{len(results)} rezultate găsite")
            _render_results()

        search_btn.on("click", do_search)
        query_input.on("keydown.enter", do_search)

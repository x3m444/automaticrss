import threading
from nicegui import ui, run
from ui.layout import navbar
from core.scrapers import SCRAPERS
from core.db import Session, Setting, Watchlist


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
                            ui.chip(
                                sd, clickable=True,
                                on_click=lambda s=sd: subdir_input.set_value(s),
                            ).props("dense outline")

                ui.separator()

                with ui.row().classes("justify-end gap-2 items-center"):
                    ui.button("Anulează", on_click=dlg.close).props("flat")

                    async def do_download():
                        subdir = subdir_input.value.strip() or None
                        dl_btn.props("loading")
                        ok, msg = await run.io_bound(_send_download_sync, item, subdir)
                        dl_btn.props(remove="loading")
                        dlg.close()
                        if ok:
                            ui.notify(f"✓ Trimis → {msg}", type="positive", timeout=4000)
                        else:
                            ui.notify(f"Eroare: {msg}", type="negative", timeout=6000)

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

            with results_container:
                ui.label(f"{len(results)} rezultate").classes("text-sm text-gray-400")

                cols = [
                    {"name": "source",   "label": "Sursă",   "field": "source",   "align": "left", "sortable": True},
                    {"name": "title",    "label": "Titlu",    "field": "title",    "align": "left", "sortable": True},
                    {"name": "size",     "label": "Mărime",   "field": "size",     "sortable": True},
                    {"name": "seeders",  "label": "Seederi",  "field": "seeders",  "sortable": True},
                    {"name": "leechers", "label": "Leechers", "field": "leechers", "sortable": True},
                    {"name": "actions",  "label": "",         "field": "idx"},
                ]

                rows = [
                    {
                        "idx":      i,
                        "source":   r.get("source", ""),
                        "title":    r.get("title", ""),
                        "size":     r.get("size", ""),
                        "seeders":  r.get("seeders", 0),
                        "leechers": r.get("leechers", 0),
                    }
                    for i, r in enumerate(results)
                ]

                tbl = ui.table(
                    columns=cols, rows=rows, row_key="idx",
                    pagination={"rowsPerPage": 25, "sortBy": "seeders", "descending": True},
                ).classes("w-full")
                tbl.props("dense")

                tbl.add_slot("body-cell-source", """
                    <q-td :props="props">
                        <q-badge color="purple" outline>{{ props.value }}</q-badge>
                    </q-td>
                """)
                tbl.add_slot("body-cell-title", """
                    <q-td :props="props"
                          style="max-width:420px;white-space:normal;word-break:break-word">
                        {{ props.value }}
                    </q-td>
                """)
                tbl.add_slot("body-cell-seeders", """
                    <q-td :props="props">
                        <span :style="{color: props.value > 0 ? '#4caf50' : '#9e9e9e'}">
                            {{ props.value }}
                        </span>
                    </q-td>
                """)
                tbl.add_slot("body-cell-actions", """
                    <q-td :props="props">
                        <q-btn flat dense icon="download" color="primary"
                            @click="$parent.$emit('dl', props.row)" />
                    </q-td>
                """)

                tbl.on("dl", lambda e: _show_download_dialog(
                    state["results"][int(e.args["idx"])]
                ))

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

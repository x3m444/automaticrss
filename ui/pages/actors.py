import threading
from nicegui import ui, run
from ui.layout import navbar
from core.scrapers import SCRAPERS


def _search_torrents(query: str, flaresolverr: str | None) -> list[dict]:
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

    threads = [threading.Thread(target=search_one, args=(sc_id,), daemon=True) for sc_id in SCRAPERS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return sorted(found, key=lambda x: x.get("seeders", 0), reverse=True)


def _send_download(item: dict, subdir: str | None) -> tuple[bool, str]:
    try:
        from transmission_rpc import Client
        from core.instance import get_instance
        inst = get_instance()
        base_dir = inst["download_dir"] or ""
        client = Client(
            host=inst["transmission_host"], port=inst["transmission_port"],
            username=inst["transmission_user"], password=inst["transmission_pass"],
        )
        download_dir = f"{base_dir.rstrip('/')}/{subdir}" if subdir and base_dir else base_dir or None
        magnet = item.get("magnet") or ""
        getter = item.get("_magnet_getter")
        if not magnet.startswith("magnet:") and getter:
            magnet = getter() or ""
        if not magnet.startswith("magnet:"):
            return False, "Niciun magnet disponibil"
        kwargs = {"download_dir": download_dir} if download_dir else {}
        t = client.add_torrent(magnet, **kwargs)
        from core.db import Session, Download
        with Session() as s:
            if not s.query(Download).filter_by(torrent_hash=t.hashString).first():
                s.add(Download(torrent_hash=t.hashString, title=item.get("title", ""), status="queued"))
                s.commit()
        return True, download_dir or "director default"
    except Exception as e:
        return False, str(e)


def _get_flaresolverr() -> str | None:
    from core.db import Session, Setting
    with Session() as s:
        row = s.query(Setting).filter_by(key="flaresolverr_url").first()
        return row.value if row and row.value else None


def _fmt_size(n: int) -> str:
    if not n:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@ui.page("/actors")
def actors_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-6"):
        ui.label("Căutare Actor / Actriță").classes("text-2xl font-bold")

        with ui.row().classes("w-full items-center gap-3 max-w-xl"):
            search_inp = ui.input(placeholder="ex: Mia Malkova, Lana Rhoades…").classes("flex-1")
            search_btn = ui.button("Caută", icon="search").props("color=primary")

        status_lbl  = ui.label("").classes("text-sm text-gray-400")
        results_col = ui.column().classes("w-full gap-4")

        async def do_search(_=None):
            query = search_inp.value.strip()
            if not query:
                return
            search_btn.props("loading")
            status_lbl.set_text("Se caută…")
            results_col.clear()

            def _fetch():
                from core.scrapers.iafd import search_performer, get_performer_details
                basic = search_performer(query)
                if not basic:
                    return None
                return get_performer_details(basic["iafd_url"])

            result = await run.io_bound(_fetch)
            search_btn.props(remove="loading")

            if not result:
                status_lbl.set_text("Niciun rezultat găsit.")
                return

            status_lbl.set_text(f"{len(result['movies'])} filme găsite pentru {result['name']}")
            _render_result(results_col, result)

        search_inp.on("keydown.enter", do_search)
        search_btn.on("click", do_search)


def _render_result(container, result: dict):
    bio = result.get("bio", {})

    with container:
        # ── Card performer ───────────────────────────────────────────────
        with ui.card().classes("w-full max-w-4xl"):
            with ui.row().classes("items-start gap-6"):
                if result.get("photo_url"):
                    ui.image(result["photo_url"]).classes("w-32 h-32 rounded-lg object-cover shrink-0")
                else:
                    ui.icon("person", size="5rem").classes("text-gray-400 shrink-0")

                with ui.column().classes("gap-1 flex-1"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(result["name"]).classes("text-xl font-bold")
                        if result.get("iafd_url"):
                            ui.link("IAFD", result["iafd_url"], new_tab=True).classes("text-xs text-blue-400")

                    ui.label(f"{len(result['movies'])} filme în filmografie").classes("text-sm text-gray-400")

                    if bio:
                        with ui.row().classes("flex-wrap gap-x-6 gap-y-1 mt-2"):
                            for key, label in [
                                ("measurements", "Măsuri"), ("height", "Înălțime"),
                                ("nationality", "Naționalitate"), ("hair", "Păr"),
                                ("ethnicity", "Etnicitate"),
                            ]:
                                if bio.get(key):
                                    with ui.row().classes("gap-1 items-center"):
                                        ui.label(f"{label}:").classes("text-xs text-gray-500")
                                        ui.label(bio[key]).classes("text-xs font-medium")

        # ── Lista filme ──────────────────────────────────────────────────
        with ui.card().classes("w-full max-w-4xl"):
            ui.label("Filmografie — apasă Caută pentru torrente").classes("text-lg font-semibold mb-2")

            for movie in result["movies"]:
                with ui.column().classes("w-full gap-0"):
                    torrent_area = ui.column().classes("w-full")

                    with ui.row().classes("w-full items-center gap-3 py-1"):
                        ui.label(movie["year"]).classes("text-xs text-gray-400 w-10 shrink-0")
                        with ui.column().classes("flex-1 gap-0"):
                            ui.label(movie["title"]).classes("text-sm")
                            if movie.get("distributor"):
                                ui.label(movie["distributor"]).classes("text-xs text-gray-500")
                        ui.link("IAFD", movie["iafd_url"], new_tab=True).classes("text-xs text-gray-500 shrink-0")

                        async def cauta_torrente(title=movie["title"], area=torrent_area, actor=result["name"]):
                            area.clear()
                            with area:
                                ui.spinner(size="sm")
                            flare = await run.io_bound(_get_flaresolverr)
                            results = await run.io_bound(_search_torrents, title, flare)
                            area.clear()
                            if not results:
                                with area:
                                    ui.label("Niciun torrent găsit.").classes("text-xs text-gray-400 pl-12")
                                return
                            with area:
                                _render_torrents(results[:8], title, actor)

                        ui.button("Caută", on_click=cauta_torrente).props("outline dense size=sm color=primary")

                    ui.separator().classes("opacity-20")


def _render_torrents(results: list[dict], movie_title: str, actor_name: str = ""):
    subdir = f"actors/{actor_name}".strip("/") if actor_name else "actors"

    for r in results:
        title = r.get("title", movie_title)
        size  = _fmt_size(r.get("size_bytes", 0))
        seeds = r.get("seeders", 0)
        src   = r.get("source", "")

        with ui.row().classes("w-full items-center gap-2 pl-12 py-1 text-xs"):
            ui.label(title).classes("flex-1 truncate text-gray-300")
            if size:
                ui.label(size).classes("text-gray-500 shrink-0")
            ui.badge(f"▲{seeds}", color="green" if seeds > 5 else "orange").props("outline")
            if src:
                ui.label(src).classes("text-gray-600 shrink-0")

            async def do_download(item=r, sd=subdir):
                ok, msg = await run.io_bound(_send_download, item, sd)
                if ok:
                    ui.notify(f"✓ Adăugat → {sd}", type="positive")
                else:
                    ui.notify(f"✘ {msg}", type="negative", timeout=8000)

            ui.button(icon="download", on_click=do_download).props("flat dense round color=primary")

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

    state: dict = {"performer": None, "slug": "", "page": 1, "last_page": 1, "total": 0}

    with ui.column().classes("w-full p-6 gap-6"):
        ui.label("Căutare Actor / Actriță").classes("text-2xl font-bold")

        with ui.row().classes("w-full items-center gap-3 max-w-xl"):
            search_inp = ui.input(placeholder="ex: Mia Malkova, Lana Rhoades…").classes("flex-1")
            search_btn = ui.button("Caută", icon="search").props("color=primary")

        status_lbl    = ui.label("").classes("text-sm text-gray-400")
        performer_col = ui.column().classes("w-full max-w-5xl gap-4")
        movies_col    = ui.column().classes("w-full max-w-5xl")

        async def do_search(_=None):
            query = search_inp.value.strip()
            if not query:
                return
            search_btn.props("loading")
            status_lbl.set_text("Se caută…")
            performer_col.clear()
            movies_col.clear()

            def _fetch():
                from core.scrapers.tpdb import search_performer, get_movies
                perf = search_performer(query)
                if not perf:
                    return None, None
                movies_data = get_movies(perf["slug"], page=1, per_page=24)
                return perf, movies_data

            perf, movies_data = await run.io_bound(_fetch)
            search_btn.props(remove="loading")

            if not perf:
                status_lbl.set_text("Niciun rezultat găsit.")
                return

            state["performer"] = perf
            state["slug"]      = perf["slug"]
            state["page"]      = 1
            state["last_page"] = movies_data["last_page"]
            state["total"]     = movies_data["total"]

            status_lbl.set_text(
                f"{movies_data['total']} filme găsite pentru {perf['name']}"
            )
            _render_performer(performer_col, perf)
            _render_movies(movies_col, movies_data["movies"], perf["name"], state, movies_col)

        search_inp.on("keydown.enter", do_search)
        search_btn.on("click", do_search)


def _render_performer(container, perf: dict):
    extras = perf.get("extras") or {}
    with container:
        with ui.card().classes("w-full"):
            with ui.row().classes("items-start gap-6"):
                if perf.get("photo_url"):
                    ui.image(perf["photo_url"]).classes("w-36 h-48 rounded-lg object-cover shrink-0")
                else:
                    ui.icon("person", size="6rem").classes("text-gray-400 shrink-0")

                with ui.column().classes("gap-2 flex-1"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(perf["name"]).classes("text-2xl font-bold")
                        if perf.get("rating"):
                            ui.badge(f"★ {perf['rating']}", color="amber")

                    bio_items = [
                        ("Măsuri",      extras.get("measurements")),
                        ("Înălțime",    extras.get("height")),
                        ("Greutate",    extras.get("weight")),
                        ("Naționalitate", extras.get("nationality")),
                        ("Etnicitate",  extras.get("ethnicity")),
                        ("Păr",         extras.get("hair")),
                        ("Ochi",        extras.get("eye_color")),
                        ("Loc naștere", extras.get("birthplace")),
                        ("Activă",      f"{extras['career_start']} – {extras.get('career_end') or 'prezent'}"
                                        if extras.get("career_start") else None),
                    ]
                    with ui.row().classes("flex-wrap gap-x-6 gap-y-1"):
                        for label, val in bio_items:
                            if val:
                                with ui.row().classes("gap-1 items-center"):
                                    ui.label(f"{label}:").classes("text-xs text-gray-500")
                                    ui.label(val).classes("text-xs font-medium")

                    if perf.get("bio"):
                        ui.label(perf["bio"][:300] + "…" if len(perf.get("bio", "")) > 300 else perf.get("bio", "")) \
                          .classes("text-xs text-gray-400 mt-2 max-w-2xl")


def _render_movies(container, movies: list[dict], actor_name: str, state: dict, movies_col):
    with container:
        # Grid de posteri
        with ui.grid().classes("w-full grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3"):
            for movie in movies:
                _render_movie_card(movie, actor_name)

        # Paginare
        if state["last_page"] > 1:
            with ui.row().classes("w-full justify-center items-center gap-4 mt-4"):
                ui.label(f"Pagina {state['page']} din {state['last_page']}").classes("text-sm text-gray-400")

                async def prev_page():
                    if state["page"] <= 1:
                        return
                    state["page"] -= 1
                    await _load_page(state, movies_col, actor_name)

                async def next_page():
                    if state["page"] >= state["last_page"]:
                        return
                    state["page"] += 1
                    await _load_page(state, movies_col, actor_name)

                ui.button(icon="chevron_left", on_click=prev_page).props(
                    "outline round dense"
                ).bind_enabled_from(state, "page", lambda p: p > 1)
                ui.button(icon="chevron_right", on_click=next_page).props(
                    "outline round dense"
                ).bind_enabled_from(state, "page", lambda p: p < state["last_page"])


async def _load_page(state: dict, container, actor_name: str):
    container.clear()

    def _fetch():
        from core.scrapers.tpdb import get_movies
        return get_movies(state["slug"], page=state["page"], per_page=24)

    data = await run.io_bound(_fetch)
    _render_movies(container, data["movies"], actor_name, state, container)


def _render_movie_card(movie: dict, actor_name: str):
    subdir = f"actors/{actor_name}".strip("/")

    with ui.card().classes("cursor-pointer hover:shadow-lg transition-shadow p-0 overflow-hidden"):
        torrent_dialog = [None]

        def open_torrent_dialog(m=movie):
            with ui.dialog() as dlg, ui.card().classes("w-full max-w-2xl"):
                torrent_dialog[0] = dlg
                with ui.row().classes("w-full justify-between items-center mb-2"):
                    ui.label(m["title"]).classes("font-bold text-sm flex-1 truncate")
                    ui.button(icon="close", on_click=dlg.close).props("flat dense round")

                spinner_row = ui.row().classes("w-full justify-center py-4")
                with spinner_row:
                    ui.spinner()

                results_col = ui.column().classes("w-full gap-1")

                async def load_torrents():
                    flare = await run.io_bound(_get_flaresolverr)
                    results = await run.io_bound(_search_torrents, m["title"], flare)
                    spinner_row.clear()
                    if not results:
                        with results_col:
                            ui.label("Niciun torrent găsit.").classes("text-sm text-gray-400 py-4 text-center w-full")
                        return
                    with results_col:
                        for r in results[:10]:
                            _render_torrent_row(r, subdir)

                ui.timer(0.1, load_torrents, once=True)
                dlg.open()

        if movie.get("poster"):
            ui.image(movie["poster"]).classes("w-full aspect-video object-cover")
        else:
            with ui.element("div").classes("w-full aspect-video bg-gray-800 flex items-center justify-center"):
                ui.icon("movie", size="2rem").classes("text-gray-600")

        with ui.column().classes("p-2 gap-0"):
            ui.label(movie["title"]).classes("text-xs font-medium line-clamp-2 leading-tight")
            with ui.row().classes("w-full items-center justify-between mt-1"):
                ui.label(movie["year"]).classes("text-xs text-gray-500")
                ui.button(
                    icon="search", on_click=open_torrent_dialog
                ).props("flat dense round color=primary size=xs").tooltip("Caută torrente")


def _render_torrent_row(r: dict, subdir: str):
    title = r.get("title", "")
    size  = _fmt_size(r.get("size_bytes", 0))
    seeds = r.get("seeders", 0)
    src   = r.get("source", "")

    with ui.row().classes("w-full items-center gap-2 py-1 text-xs border-b border-gray-800"):
        with ui.column().classes("flex-1 gap-0 min-w-0"):
            ui.label(title).classes("truncate text-gray-300 text-xs")
            with ui.row().classes("gap-3 items-center"):
                if size:
                    ui.label(size).classes("text-gray-500")
                if src:
                    ui.label(src).classes("text-gray-600")
        ui.badge(f"▲{seeds}", color="green" if seeds > 5 else "orange").props("outline")

        async def do_download(item=r, sd=subdir):
            ok, msg = await run.io_bound(_send_download, item, sd)
            if ok:
                ui.notify(f"✓ Adăugat → {sd}", type="positive")
            else:
                ui.notify(f"✘ {msg}", type="negative", timeout=8000)

        ui.button(icon="download", on_click=do_download).props("flat dense round color=primary size=xs")

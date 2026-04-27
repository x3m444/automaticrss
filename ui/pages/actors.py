import threading
from nicegui import ui, run
from ui.layout import navbar
from core.scrapers import SCRAPERS

SORT_OPTIONS = {
    "created_at|desc": "Recente",
    "date|desc":       "Data (desc)",
    "rating|desc":     "Rating",
    "title|asc":       "Titlu A→Z",
    "title|desc":      "Titlu Z→A",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

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


def _fmt_duration(secs: int | None) -> str:
    if not secs:
        return ""
    h, m = divmod(secs // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def _parse_sort(val: str) -> tuple[str, str]:
    parts = val.split("|")
    return (parts[0], parts[1]) if len(parts) == 2 else ("created_at", "desc")


# ── Autocomplete widget ───────────────────────────────────────────────────────

def _make_autocomplete(placeholder: str, fetch_fn, result_state: dict, key: str) -> ui.input:
    """
    Builds an input with live-search dropdown.
    fetch_fn(text) → list[{id, name}]
    On selection stores {id, name} into result_state[key].
    """
    inp = ui.input(placeholder=placeholder).classes("w-48")
    menu = ui.menu().props("no-parent-event")

    def _pick(name: str, item_id):
        inp.set_value(name)
        result_state[key] = {"id": item_id, "name": name}
        menu.close()

    def _clear(_=None):
        if inp.value.strip() == "":
            result_state[key] = None
            menu.close()

    async def on_keyup(_=None):
        text = inp.value.strip()
        if len(text) < 2:
            menu.close()
            if text == "":
                result_state[key] = None
            return
        results = await run.io_bound(lambda: fetch_fn(text))
        menu.clear()
        with menu:
            for r in results[:10]:
                name, rid = r["name"], r["id"]
                ui.menu_item(name, on_click=lambda n=name, i=rid: _pick(n, i))
        if results:
            menu.open()
        else:
            menu.close()

    inp.on("keyup", on_keyup)
    inp.on("change", _clear)
    return inp


# ── Page ────────────────────────────────────────────────────────────────────

@ui.page("/actors")
def actors_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-4"):
        ui.label("Descoperă").classes("text-2xl font-bold")

        with ui.tabs().classes("w-full") as tabs:
            tab_performer     = ui.tab("Performer")
            tab_film          = ui.tab("Caută Film")
            tab_film_recente  = ui.tab("Recente Filme")
            tab_scene         = ui.tab("Caută Scenă")
            tab_scene_recente = ui.tab("Recente Scene")

        with ui.tab_panels(tabs, value=tab_performer).classes("w-full"):
            with ui.tab_panel(tab_performer):
                _build_performer_tab()
            with ui.tab_panel(tab_film):
                _build_search_tab("movies")
            with ui.tab_panel(tab_film_recente):
                _build_recent_tab("movies")
            with ui.tab_panel(tab_scene):
                _build_search_tab("scenes")
            with ui.tab_panel(tab_scene_recente):
                _build_recent_tab("scenes")


# ── Tab: Performer ───────────────────────────────────────────────────────────

def _build_performer_tab():
    state: dict = {"slug": "", "page": 1, "last_page": 1, "total": 0}

    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("w-full items-center gap-3 max-w-xl"):
            inp = ui.input(placeholder="ex: Mia Malkova, Lana Rhoades…").classes("flex-1")
            btn = ui.button("Caută", icon="search").props("color=primary")

        status_lbl    = ui.label("").classes("text-sm text-gray-400")
        performer_col = ui.column().classes("w-full max-w-5xl")
        movies_col    = ui.column().classes("w-full max-w-5xl")

        async def do_search(_=None):
            query = inp.value.strip()
            if not query:
                return
            btn.props("loading")
            status_lbl.set_text("Se caută…")
            performer_col.clear()
            movies_col.clear()

            def _fetch():
                from core.scrapers.tpdb import search_performer, get_movies
                perf = search_performer(query)
                if not perf:
                    return None, None
                return perf, get_movies(perf["slug"], page=1, per_page=24)

            perf, movies_data = await run.io_bound(_fetch)
            btn.props(remove="loading")

            if not perf:
                status_lbl.set_text("Niciun rezultat găsit.")
                return

            state.update(slug=perf["slug"], page=1,
                         last_page=movies_data["last_page"], total=movies_data["total"])
            status_lbl.set_text(f"{movies_data['total']} filme pentru {perf['name']}")
            _render_performer(performer_col, perf)
            _render_media_grid(movies_col, movies_data["movies"], "movies", perf["name"], state, movies_col)

        inp.on("keydown.enter", do_search)
        btn.on("click", do_search)


# ── Tab: Caută Film / Scenă ──────────────────────────────────────────────────

def _build_search_tab(media_type: str):
    is_movie  = media_type == "movies"
    ph        = "ex: Anal, Mia Malkova Experience…" if is_movie else "ex: Mia Malkova, Big Tits…"
    found_lbl = "filme" if is_movie else "scene"

    state: dict = {"page": 1, "last_page": 1}
    filters: dict = {"site": None, "performer": None}  # each: {id, name} or None

    from core.scrapers.tpdb import search_sites, search_performers_lite

    with ui.column().classes("w-full gap-3"):
        # ── search row
        with ui.row().classes("w-full items-center gap-3 flex-wrap max-w-4xl"):
            inp = ui.input(placeholder=ph).classes("flex-1 min-w-48")
            btn = ui.button("Caută", icon="search").props("color=primary")

        # ── filter row
        with ui.row().classes("w-full items-center gap-3 flex-wrap max-w-4xl"):
            ui.label("Filtre:").classes("text-xs text-gray-500")
            _make_autocomplete("Studio (ex: Brazzers)",  search_sites,           filters, "site")
            _make_autocomplete("Performer (ex: Mia M.)", search_performers_lite, filters, "performer")
            sort_sel = ui.select(SORT_OPTIONS, value="created_at|desc", label="Sortare").classes("w-44")

        status_lbl  = ui.label("").classes("text-sm text-gray-400")
        results_col = ui.column().classes("w-full max-w-5xl")

        async def do_search(_=None):
            query = inp.value.strip()
            if not query:
                return
            sort, order    = _parse_sort(sort_sel.value)
            site_name      = (filters["site"] or {}).get("name", "")
            performer_id   = (filters["performer"] or {}).get("id")
            state["page"]  = 1
            btn.props("loading")
            status_lbl.set_text("Se caută…")
            results_col.clear()

            if is_movie:
                data = await run.io_bound(
                    lambda: __import__("core.scrapers.tpdb", fromlist=["search_movies"])
                            .search_movies(query, site=site_name, performer_id=performer_id,
                                           sort=sort, order=order, page=1, per_page=24)
                )
                items = data["movies"]
            else:
                data = await run.io_bound(
                    lambda: __import__("core.scrapers.tpdb", fromlist=["search_scenes"])
                            .search_scenes(query, site=site_name, performer_id=performer_id,
                                           sort=sort, order=order, page=1, per_page=24)
                )
                items = data["scenes"]

            btn.props(remove="loading")
            state["last_page"] = data["last_page"]
            status_lbl.set_text(f"{data['total']} {found_lbl} găsite")
            _render_media_grid(results_col, items, media_type, "", state, results_col)

        inp.on("keydown.enter", do_search)
        btn.on("click", do_search)


# ── Tab: Recente Filme / Scene ───────────────────────────────────────────────

def _build_recent_tab(media_type: str):
    is_movie = media_type == "movies"
    state: dict  = {"page": 1, "last_page": 1}
    filters: dict = {"site": None, "performer": None}

    from core.scrapers.tpdb import search_sites, search_performers_lite

    with ui.column().classes("w-full gap-3"):
        with ui.row().classes("w-full items-center gap-3 flex-wrap max-w-4xl"):
            ui.label("Filtre:").classes("text-xs text-gray-500")
            _make_autocomplete("Studio (ex: Brazzers)",  search_sites,           filters, "site")
            _make_autocomplete("Performer (ex: Mia M.)", search_performers_lite, filters, "performer")
            sort_sel  = ui.select(SORT_OPTIONS, value="created_at|desc", label="Sortare").classes("w-44")
            apply_btn = ui.button("Aplică", icon="filter_list").props("outline color=primary")

        status_lbl = ui.label("Se încarcă…").classes("text-sm text-gray-400")
        container  = ui.column().classes("w-full max-w-5xl")

        async def load(page: int = 1):
            state["page"] = page
            container.clear()
            status_lbl.set_text("Se încarcă…")
            sort, order  = _parse_sort(sort_sel.value)
            site_name    = (filters["site"] or {}).get("name", "")
            performer_id = (filters["performer"] or {}).get("id")

            if is_movie:
                data = await run.io_bound(
                    lambda: __import__("core.scrapers.tpdb", fromlist=["get_latest_movies"])
                            .get_latest_movies(site=site_name, performer_id=performer_id,
                                               sort=sort, order=order, page=page, per_page=48)
                )
                items, label = data["movies"], "Filme"
            else:
                data = await run.io_bound(
                    lambda: __import__("core.scrapers.tpdb", fromlist=["get_latest_scenes"])
                            .get_latest_scenes(site=site_name, performer_id=performer_id,
                                               sort=sort, order=order, page=page, per_page=48)
                )
                items, label = data["scenes"], "Scene"

            state["last_page"] = data["last_page"]
            status_lbl.set_text(f"{label} — pagina {page} din {data['last_page']}")
            _render_media_grid(container, items, media_type, "", state, container, on_page=load)

        async def apply_filters(_=None):
            state["page"] = 1
            await load(1)

        apply_btn.on("click", apply_filters)
        ui.timer(0.2, lambda: run.io_bound(load), once=True)


# ── Shared renderers ─────────────────────────────────────────────────────────

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
                        ("Măsuri",        extras.get("measurements")),
                        ("Înălțime",      extras.get("height")),
                        ("Greutate",      extras.get("weight")),
                        ("Naționalitate", extras.get("nationality")),
                        ("Etnicitate",    extras.get("ethnicity")),
                        ("Păr",           extras.get("hair")),
                        ("Ochi",          extras.get("eye_color")),
                        ("Loc naștere",   extras.get("birthplace")),
                        ("Activă",        f"{extras['career_start']} – {extras.get('career_end') or 'prezent'}"
                                          if extras.get("career_start") else None),
                    ]
                    with ui.row().classes("flex-wrap gap-x-6 gap-y-1"):
                        for label, val in bio_items:
                            if val:
                                with ui.row().classes("gap-1 items-center"):
                                    ui.label(f"{label}:").classes("text-xs text-gray-500")
                                    ui.label(val).classes("text-xs font-medium")

                    if perf.get("bio"):
                        bio_text = perf["bio"]
                        ui.label(bio_text[:300] + "…" if len(bio_text) > 300 else bio_text) \
                          .classes("text-xs text-gray-400 mt-2 max-w-2xl")


def _render_media_grid(container, items: list[dict], media_type: str, actor_name: str,
                       state: dict, col_ref, on_page=None):
    with container:
        with ui.grid().classes("w-full grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3"):
            for item in items:
                if actor_name:
                    subdir = f"tpdb/actors/{actor_name}"
                elif media_type == "scenes":
                    subdir = "tpdb/scenes"
                else:
                    subdir = "tpdb/movies"
                _render_card(item, subdir, media_type)

        if state.get("last_page", 1) > 1:
            with ui.row().classes("w-full justify-center items-center gap-4 mt-4"):
                ui.label(f"Pagina {state['page']} din {state['last_page']}").classes("text-sm text-gray-400")

                async def prev_page(s=state, mc=col_ref, an=actor_name, op=on_page):
                    if s["page"] <= 1:
                        return
                    s["page"] -= 1
                    mc.clear()
                    if op:
                        await op(s["page"])
                    else:
                        await _reload_performer_page(s, mc, an)

                async def next_page(s=state, mc=col_ref, an=actor_name, op=on_page):
                    if s["page"] >= s["last_page"]:
                        return
                    s["page"] += 1
                    mc.clear()
                    if op:
                        await op(s["page"])
                    else:
                        await _reload_performer_page(s, mc, an)

                ui.button(icon="chevron_left",  on_click=prev_page).props("outline round dense")
                ui.button(icon="chevron_right", on_click=next_page).props("outline round dense")


async def _reload_performer_page(state: dict, container, actor_name: str):
    data = await run.io_bound(
        lambda: __import__("core.scrapers.tpdb", fromlist=["get_movies"])
                .get_movies(state["slug"], page=state["page"], per_page=24)
    )
    _render_media_grid(container, data["movies"], "movies", actor_name, state, container)


def _render_card(item: dict, subdir: str, media_type: str):
    with ui.card().classes("p-0 overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"):

        def open_dialog(m=item, sd=subdir):
            with ui.dialog() as dlg, ui.card().classes("w-full max-w-2xl"):
                with ui.row().classes("w-full justify-between items-center mb-1"):
                    with ui.column().classes("flex-1 gap-0 min-w-0"):
                        ui.label(m["title"]).classes("font-bold text-sm truncate")
                        meta_parts = []
                        if m.get("site"):
                            meta_parts.append(m["site"])
                        if m.get("date"):
                            meta_parts.append(m["date"][:10])
                        if m.get("duration"):
                            meta_parts.append(_fmt_duration(m["duration"]))
                        if meta_parts:
                            ui.label(" · ".join(meta_parts)).classes("text-xs text-gray-500")
                        if m.get("performers"):
                            ui.label(", ".join(m["performers"])).classes("text-xs text-blue-400")
                        if m.get("tags"):
                            with ui.row().classes("gap-1 flex-wrap"):
                                for tag in m["tags"]:
                                    ui.badge(tag, color="blue-grey").props("outline dense")
                    ui.button(icon="close", on_click=dlg.close).props("flat dense round")

                spinner_row = ui.row().classes("w-full justify-center py-4")
                results_col = ui.column().classes("w-full gap-0")
                with spinner_row:
                    ui.spinner()

                async def load_torrents(title=m["title"], rc=results_col, sr=spinner_row, sdir=sd):
                    flare   = await run.io_bound(_get_flaresolverr)
                    results = await run.io_bound(_search_torrents, title, flare)
                    sr.clear()
                    if not results:
                        with rc:
                            ui.label("Niciun torrent găsit.").classes(
                                "text-sm text-gray-400 py-4 text-center w-full"
                            )
                        return
                    with rc:
                        for r in results[:10]:
                            _render_torrent_row(r, sdir)

                ui.timer(0.1, load_torrents, once=True)
                dlg.open()

        if item.get("poster"):
            ui.image(item["poster"]).classes("w-full aspect-video object-cover").on("click", open_dialog)
        else:
            with ui.element("div").classes(
                "w-full aspect-video bg-gray-800 flex items-center justify-center cursor-pointer"
            ).on("click", open_dialog):
                ui.icon("movie", size="2rem").classes("text-gray-600")

        with ui.column().classes("p-2 gap-0"):
            ui.label(item["title"]).classes("text-xs font-medium line-clamp-2 leading-tight")
            with ui.row().classes("w-full items-center justify-between mt-1"):
                site_or_year = item.get("site") or item.get("year", "")
                ui.label(site_or_year).classes("text-xs text-gray-500 truncate flex-1")
                if item.get("performers"):
                    ui.label(", ".join(item["performers"][:2])).classes(
                        "text-xs text-blue-400 truncate max-w-[55%]"
                    )
                ui.button(icon="search", on_click=open_dialog).props(
                    "flat dense round color=primary size=xs"
                ).tooltip("Caută torrente")


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

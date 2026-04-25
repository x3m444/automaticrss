from nicegui import ui, run
from ui.layout import navbar
from core.rss_parser import validate_feed, fetch_feed
from core.db import Session, Feed
from core.scrapers import SCRAPERS


def _load_feeds():
    with Session() as s:
        rows = s.query(Feed).order_by(Feed.created_at.desc()).all()
        return [
            {
                "id": f.id,
                "name": f.name,
                "url": f.url,
                "source_type": f.source_type or "rss",
                "indexer_id": f.indexer_id or "",
                "categories": f.categories or [],
                "poll_interval_minutes": f.poll_interval_minutes,
                "is_active": f.is_active,
                "last_checked_at": str(f.last_checked_at or "—"),
            }
            for f in rows
        ]


def _fetch_rss(url: str) -> list[dict]:
    return fetch_feed(url)


def _fetch_scraper(feed: dict) -> list[dict]:
    from core.db import Session, Setting
    scraper_cls = SCRAPERS.get(feed["indexer_id"])
    if not scraper_cls:
        return []
    with Session() as s:
        row = s.query(Setting).filter_by(key="flaresolverr_url").first()
        flaresolverr = row.value if row and row.value else None
    cats = feed.get("categories") or []
    return scraper_cls().fetch_latest(
        categories=cats if cats else None,
        flaresolverr_url=flaresolverr,
    )


def _render_preview(items: list[dict], container, source_type: str):
    if not items:
        with container:
            msg = "Niciun item găsit — site-ul poate fi blocat (încearcă FlareSolverr)." \
                  if source_type == "scraper" else "Niciun item găsit."
            ui.label(msg).classes("text-gray-400")
        return
    if source_type == "scraper":
        rows = [{"title": i.get("title",""), "size": i.get("size",""),
                 "seeders": str(i.get("seeders","")), "leechers": str(i.get("leechers",""))}
                for i in items[:50]]
        cols = [
            {"name": "title",    "label": "Titlu",    "field": "title",    "align": "left"},
            {"name": "size",     "label": "Mărime",   "field": "size"},
            {"name": "seeders",  "label": "Seederi",  "field": "seeders"},
            {"name": "leechers", "label": "Leechers", "field": "leechers"},
        ]
        with container:
            ui.table(columns=cols, rows=rows, row_key="title", pagination=20).classes("w-full")
            ui.label(f"{len(items)} torrente găsite").classes("text-xs text-gray-400 mt-1")
    else:
        rows = [{"title": i.get("title",""), "category": i.get("category",""),
                 "published": i.get("published","")} for i in items[:50]]
        cols = [
            {"name": "title",    "label": "Titlu",     "field": "title",    "align": "left"},
            {"name": "category", "label": "Categorie", "field": "category"},
            {"name": "published","label": "Data",      "field": "published"},
        ]
        with container:
            ui.table(columns=cols, rows=rows, row_key="title", pagination=20).classes("w-full")


@ui.page("/feeds")
def feeds_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-8"):

        # ── Lista feed-uri ────────────────────────────────────────────────
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("items-center gap-3"):
                ui.label("Feed-uri active").classes("text-xl font-bold")
                feeds_count_badge = ui.badge("0").props("color=primary rounded")

            list_container = ui.column().classes("w-full gap-2")

            def refresh_list():
                list_container.clear()
                feeds = _load_feeds()
                feeds_count_badge.set_text(str(len(feeds)))

                if not feeds:
                    with list_container:
                        ui.label("Niciun feed adăugat încă.").classes("text-gray-400 text-sm")
                    return

                def do_preview(feed: dict):
                    with ui.dialog() as dlg, ui.card().classes("w-full max-w-5xl"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label(f"Preview: {feed['name']}").classes("text-lg font-bold")
                            ui.button(icon="close", on_click=dlg.close).props("flat dense round")
                        loading = ui.label("Se încarcă...").classes("text-gray-400")
                        preview_container = ui.column().classes("w-full")

                        async def load():
                            loading.set_text("")
                            try:
                                if feed["source_type"] == "scraper":
                                    items = await run.io_bound(_fetch_scraper, feed)
                                else:
                                    items = await run.io_bound(_fetch_rss, feed["url"])
                                _render_preview(items, preview_container, feed["source_type"])
                            except Exception as ex:
                                with preview_container:
                                    ui.label(f"Eroare: {ex}").classes("text-red-500")

                        ui.timer(0.1, load, once=True)
                    dlg.open()

                def do_edit(feed: dict):
                    cur_cats = list(feed.get("categories") or [])

                    with ui.dialog() as dlg, ui.card().classes("w-full max-w-lg gap-3"):
                        with ui.row().classes("w-full justify-between items-center"):
                            ui.label("Editează feed").classes("text-lg font-bold")
                            ui.button(icon="close", on_click=dlg.close).props("flat dense round")

                        name_inp = ui.input("Nume", value=feed["name"]).classes("w-full")

                        if feed["source_type"] == "rss":
                            url_inp = ui.input("URL", value=feed["url"]).classes("w-full")
                        else:
                            url_inp = None
                            sc = SCRAPERS.get(feed["indexer_id"])
                            ui.label(
                                f"Indexer: {sc.name if sc else feed['indexer_id']}"
                            ).classes("text-sm text-gray-400")

                        interval_inp = ui.number(
                            "Interval (min)", value=feed["poll_interval_minutes"], min=5
                        ).classes("w-40")
                        active_sw = ui.switch("Activ", value=feed["is_active"])

                        ui.label("Categorii").classes("text-sm font-medium mt-2")
                        chips_row = ui.row().classes("flex-wrap gap-2 min-h-8")

                        def render_cats():
                            chips_row.clear()
                            with chips_row:
                                for cat in cur_cats[:]:
                                    ui.chip(
                                        cat, removable=True, color="primary",
                                        on_value_change=lambda e, c=cat: (
                                            cur_cats.remove(c) if not e.value and c in cur_cats else None,
                                            render_cats(),
                                        ),
                                    )

                        render_cats()

                        with ui.row().classes("items-center gap-2 mt-1"):
                            cat_inp = ui.input(placeholder="categorie nouă").classes("flex-1")

                            def add_cat():
                                val = cat_inp.value.strip()
                                if val and val not in cur_cats:
                                    cur_cats.append(val)
                                    render_cats()
                                cat_inp.set_value("")

                            ui.button(icon="add", on_click=add_cat).props("flat dense round")
                            cat_inp.on("keydown.enter", lambda _: add_cat())

                        ui.separator()

                        def save():
                            with Session() as s:
                                row = s.query(Feed).filter_by(id=feed["id"]).first()
                                if row:
                                    row.name = name_inp.value.strip() or feed["name"]
                                    if url_inp:
                                        row.url = url_inp.value.strip() or feed["url"]
                                    row.poll_interval_minutes = int(interval_inp.value or 60)
                                    row.is_active = active_sw.value
                                    row.categories = cur_cats if cur_cats else None
                                    s.commit()
                            dlg.close()
                            ui.notify("✓ Feed actualizat", type="positive")
                            refresh_list()

                        with ui.row().classes("justify-end gap-2"):
                            ui.button("Anulează", on_click=dlg.close).props("flat")
                            ui.button("Salvează", on_click=save).props("color=primary")

                    dlg.open()

                def do_delete(feed: dict):
                    with Session() as s:
                        row = s.query(Feed).filter_by(id=feed["id"]).first()
                        if row:
                            s.delete(row)
                            s.commit()
                    ui.notify("Feed șters", type="warning")
                    refresh_list()

                with list_container:
                    for f in feeds:
                        sc = SCRAPERS.get(f["indexer_id"]) if f["source_type"] == "scraper" else None
                        display_url = sc.description if sc else f["url"]
                        is_rss = f["source_type"] == "rss"

                        with ui.card().classes("w-full"):
                            with ui.row().classes("w-full items-center gap-3 px-2 py-1"):
                                ui.badge(f["source_type"]).props(
                                    f"color={'blue' if is_rss else 'purple'} outline"
                                ).classes("shrink-0")

                                with ui.column().classes("flex-1 min-w-0 gap-0"):
                                    ui.label(f["name"]).classes("font-medium text-sm")
                                    ui.label(display_url[:80]).classes("text-xs text-gray-500").style(
                                        "overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
                                    )

                                ui.label(f"{f['poll_interval_minutes']}min").classes(
                                    "text-xs text-gray-400 shrink-0"
                                )
                                ui.badge("activ" if f["is_active"] else "oprit").props(
                                    f"color={'green' if f['is_active'] else 'grey'}"
                                ).classes("shrink-0")

                                ui.button(
                                    icon="visibility",
                                    on_click=lambda feed=f: do_preview(feed),
                                ).props("flat dense round color=primary")
                                ui.button(
                                    icon="edit",
                                    on_click=lambda feed=f: do_edit(feed),
                                ).props("flat dense round color=orange")
                                ui.button(
                                    icon="delete",
                                    on_click=lambda feed=f: do_delete(feed),
                                ).props("flat dense round color=red")

            refresh_list()

        ui.separator()

        # ── Adaugă RSS ────────────────────────────────────────────────────
        with ui.column().classes("w-full gap-2"):
            ui.label("Adaugă feed RSS").classes("text-xl font-bold")

            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                    url_input  = ui.input("URL Feed RSS").classes("flex-1 min-w-64")
                    name_input = ui.input("Nume prietenos").classes("flex-1 min-w-48")
                    interval   = ui.number("Interval (min)", value=60, min=5).classes("w-32")
                    ui.button("Validează", on_click=lambda: on_validate()).props("outline")
                    ui.button("Salvează",  on_click=lambda: on_save())

                validate_status  = ui.label("").classes("text-sm text-gray-500")
                categories_panel = ui.column().classes("w-full gap-1 hidden")
                selected_cats: dict = {"checkboxes": {}}

                def on_validate():
                    validate_status.set_text("Se verifică...")
                    validate_status.classes(replace="text-sm text-gray-500")
                    categories_panel.classes(add="hidden")
                    categories_panel.clear()
                    selected_cats["checkboxes"] = {}

                    ok, msg = validate_feed(url_input.value)
                    if not ok:
                        validate_status.set_text(f"✘ {msg}")
                        validate_status.classes(replace="text-sm text-red-600")
                        return

                    validate_status.set_text(f"✔ {msg}")
                    validate_status.classes(replace="text-sm text-green-600")

                    items = fetch_feed(url_input.value)
                    cats  = sorted(set(i["category"] for i in items if i.get("category")))
                    categories_panel.classes(remove="hidden")
                    with categories_panel:
                        if cats:
                            ui.label("Filtrează categorii (gol = toate):").classes("text-xs text-gray-400")
                            with ui.row().classes("flex-wrap gap-3"):
                                for cat in cats:
                                    selected_cats["checkboxes"][cat] = ui.checkbox(cat)
                        else:
                            ui.label("Nicio categorie detectată — se indexează tot feed-ul.").classes("text-xs text-gray-400")

                def on_save():
                    if not url_input.value or not name_input.value:
                        ui.notify("Completează URL și nume", type="warning")
                        return
                    cats = [c for c, cb in selected_cats["checkboxes"].items() if cb.value]
                    with Session() as s:
                        s.add(Feed(
                            name=name_input.value,
                            url=url_input.value,
                            source_type="rss",
                            poll_interval_minutes=int(interval.value),
                            categories=cats if cats else None,
                            is_active=True,
                        ))
                        s.commit()
                    url_input.set_value("")
                    name_input.set_value("")
                    validate_status.set_text("")
                    categories_panel.classes(add="hidden")
                    selected_cats["checkboxes"] = {}
                    refresh_list()
                    ui.notify("✓ Feed adăugat", type="positive", timeout=3000)
                    ui.run_javascript("window.scrollTo({top: 0, behavior: 'smooth'})")

        ui.separator()

        # ── Adaugă Indexer (scraper) ──────────────────────────────────────
        with ui.column().classes("w-full gap-2"):
            ui.label("Adaugă Indexer").classes("text-xl font-bold")
            ui.label("Indexeri custom cu scraping direct — nu necesită Jackett.").classes("text-sm text-gray-400")

            with ui.card().classes("w-full gap-3"):
                scraper_options = {sc_id: cls.name for sc_id, cls in SCRAPERS.items()}
                first_id = list(scraper_options.keys())[0] if scraper_options else None

                with ui.row().classes("items-end gap-4 flex-wrap"):
                    sc_select   = ui.select(scraper_options, label="Indexer", value=first_id).classes("w-56")
                    sc_name_input = ui.input("Nume (opțional)").classes("flex-1 min-w-48")
                    sc_interval = ui.number("Interval (min)", value=60, min=5).classes("w-32")

                sc_desc = ui.label("").classes("text-xs text-gray-400")

                # ── Categorii custom (chip input) ──────────────────────
                ui.separator()
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Categorii (gol = toate)").classes("text-sm font-medium")
                    hint_label = ui.label("").classes("text-xs text-gray-500")

                # chips afișate
                added_cats: list[str] = []
                chips_row = ui.row().classes("flex-wrap gap-2 min-h-8")

                def render_chips():
                    chips_row.clear()
                    with chips_row:
                        for cat in added_cats:
                            ui.chip(
                                cat, removable=True, color="primary",
                                on_value_change=lambda e, c=cat: (
                                    added_cats.remove(c) if c in added_cats else None,
                                    render_chips(),
                                ),
                            )

                # input + buton add
                with ui.row().classes("items-center gap-2"):
                    cat_input = ui.input(placeholder="ex: 207  sau  all").classes("w-36")
                    ui.button(icon="add", on_click=lambda: _add_cat()).props("flat dense round")

                def _add_cat():
                    val = cat_input.value.strip()
                    if val and val not in added_cats:
                        added_cats.append(val)
                        render_chips()
                    cat_input.set_value("")

                cat_input.on("keydown.enter", lambda _: _add_cat())

                # referință categorii cunoscute pentru indexerul selectat
                ref_label = ui.label("").classes("text-xs text-gray-500 italic")
                ref_panel = ui.column().classes("w-full gap-1")

                def update_scraper_ui():
                    sc_id = sc_select.value
                    cls = SCRAPERS.get(sc_id)
                    sc_desc.set_text(cls.description if cls else "")
                    sc_name_input.set_value("")
                    added_cats.clear()
                    render_chips()
                    ref_panel.clear()

                    if not cls or not cls.categories:
                        ref_label.set_text("")
                        hint_label.set_text("")
                        return

                    hint_label.set_text("scrieți ID-ul și apăsați Enter sau +")
                    ref_label.set_text("Categorii cunoscute pentru acest indexer:")
                    with ref_panel:
                        rows = [{"id": cid, "name": cname} for cid, cname in cls.categories.items()]
                        cols = [
                            {"name": "id",   "label": "ID",   "field": "id",   "align": "left"},
                            {"name": "name", "label": "Nume", "field": "name", "align": "left"},
                        ]
                        tbl = ui.table(columns=cols, rows=rows, row_key="id").classes("w-full max-w-sm")
                        tbl.props("dense flat bordered")
                        tbl.add_slot("body-cell-id", """
                            <q-td :props="props">
                                <q-chip dense clickable color="primary" text-color="white"
                                    @click="$parent.$emit('pick', props.row)">
                                    {{ props.value }}
                                </q-chip>
                            </q-td>
                        """)
                        tbl.on("pick", lambda e: (
                            added_cats.append(e.args["id"]) if e.args["id"] not in added_cats else None,
                            render_chips(),
                        ))

                sc_select.on_value_change(lambda _: update_scraper_ui())
                update_scraper_ui()

                ui.separator()

                def add_scraper():
                    sc_id = sc_select.value
                    cls = SCRAPERS.get(sc_id)
                    if not cls:
                        ui.notify("Selectează un indexer", type="warning")
                        return

                    # build name: custom > auto-generated from cats > default
                    custom_name = sc_name_input.value.strip()
                    if custom_name:
                        feed_name = custom_name
                    elif added_cats:
                        cats_label = ", ".join(
                            cls.categories.get(c, c) for c in added_cats[:3]
                        )
                        suffix = f" +{len(added_cats)-3}" if len(added_cats) > 3 else ""
                        feed_name = f"{cls.name} — {cats_label}{suffix}"
                    else:
                        feed_name = cls.name

                    with Session() as s:
                        s.add(Feed(
                            name=feed_name,
                            url=cls.base_url,
                            source_type="scraper",
                            indexer_id=sc_id,
                            poll_interval_minutes=int(sc_interval.value),
                            categories=added_cats[:] if added_cats else None,
                            is_active=True,
                        ))
                        s.commit()
                    sc_name_input.set_value("")
                    refresh_list()
                    ui.notify(f"✓ {feed_name} adăugat", type="positive", timeout=3000)
                    ui.run_javascript("window.scrollTo({top: 0, behavior: 'smooth'})")

                with ui.row().classes("mt-3"):
                    ui.button("Adaugă", on_click=add_scraper)

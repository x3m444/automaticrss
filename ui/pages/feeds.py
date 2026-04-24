from nicegui import ui
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


def _preview_rss(feed: dict, container):
    from nicegui import ui
    items = fetch_feed(feed["url"])
    if not items:
        with container:
            ui.label("Niciun item găsit.").classes("text-gray-400")
        return
    rows = [
        {
            "title":    i.get("title", ""),
            "category": i.get("category", ""),
            "published": i.get("published", ""),
        }
        for i in items[:50]
    ]
    with container:
        cols = [
            {"name": "title",    "label": "Titlu",     "field": "title",    "align": "left"},
            {"name": "category", "label": "Categorie", "field": "category"},
            {"name": "published","label": "Data",      "field": "published"},
        ]
        ui.table(columns=cols, rows=rows, row_key="title", pagination=20).classes("w-full")


def _preview_scraper(feed: dict, container):
    from nicegui import ui
    from core.db import Session, Setting

    scraper_cls = SCRAPERS.get(feed["indexer_id"])
    if not scraper_cls:
        with container:
            ui.label(f"Scraper necunoscut: {feed['indexer_id']}").classes("text-red-500")
        return

    with Session() as s:
        row = s.query(Setting).filter_by(key="flaresolverr_url").first()
        flaresolverr = row.value if row and row.value else None

    scraper = scraper_cls()
    cats = feed.get("categories") or []
    items = scraper.fetch_latest(
        categories=cats if cats else None,
        flaresolverr_url=flaresolverr,
    )

    if not items:
        with container:
            ui.label("Niciun item găsit — site-ul poate fi blocat (încearcă FlareSolverr).").classes("text-gray-400")
        return

    rows = [
        {
            "title":    i.get("title", ""),
            "size":     i.get("size", ""),
            "seeders":  str(i.get("seeders", "")),
            "leechers": str(i.get("leechers", "")),
        }
        for i in items[:50]
    ]
    with container:
        cols = [
            {"name": "title",    "label": "Titlu",    "field": "title",    "align": "left"},
            {"name": "size",     "label": "Mărime",   "field": "size"},
            {"name": "seeders",  "label": "Seederi",  "field": "seeders"},
            {"name": "leechers", "label": "Leechers", "field": "leechers"},
        ]
        ui.table(columns=cols, rows=rows, row_key="title", pagination=20).classes("w-full")
        ui.label(f"{len(items)} torrente găsite").classes("text-xs text-gray-400 mt-1")


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

                with list_container:
                    columns = [
                        {"name": "name",     "label": "Nume",     "field": "name",     "align": "left"},
                        {"name": "type",     "label": "Tip",      "field": "source_type"},
                        {"name": "url",      "label": "URL / Indexer", "field": "url", "align": "left"},
                        {"name": "interval", "label": "Interval", "field": "poll_interval_minutes"},
                        {"name": "last",     "label": "Ultima verificare", "field": "last_checked_at"},
                        {"name": "active",   "label": "Activ",    "field": "is_active"},
                        {"name": "actions",  "label": "",         "field": "id"},
                    ]
                    rows = []
                    for f in feeds:
                        display_url = f["url"]
                        if f["source_type"] == "scraper" and f["indexer_id"]:
                            sc = SCRAPERS.get(f["indexer_id"])
                            display_url = sc.description if sc else f["indexer_id"]
                        rows.append({**f, "url": display_url})

                    tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")

                    tbl.add_slot("body-cell-type", """
                        <q-td :props="props">
                            <q-badge :color="props.value === 'rss' ? 'blue' : 'purple'" outline>
                                {{ props.value }}
                            </q-badge>
                        </q-td>
                    """)
                    tbl.add_slot("body-cell-active", """
                        <q-td :props="props">
                            <q-badge :color="props.value ? 'green' : 'grey'">
                                {{ props.value ? 'activ' : 'oprit' }}
                            </q-badge>
                        </q-td>
                    """)
                    tbl.add_slot("body-cell-actions", """
                        <q-td :props="props">
                            <q-btn flat dense icon="visibility" color="primary"
                                @click="$parent.$emit('preview', props.row)" />
                            <q-btn flat dense icon="delete" color="red"
                                @click="$parent.$emit('delete', props.row)" />
                        </q-td>
                    """)

                    def handle_delete(e):
                        with Session() as s:
                            row = s.query(Feed).filter_by(id=e.args["id"]).first()
                            if row:
                                s.delete(row)
                                s.commit()
                        ui.notify("Feed șters", type="warning")
                        refresh_list()

                    def handle_preview(e):
                        feed = e.args
                        with ui.dialog() as dlg, ui.card().classes("w-full max-w-5xl"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(f"Preview: {feed['name']}").classes("text-lg font-bold")
                                ui.button(icon="close", on_click=dlg.close).props("flat dense round")
                            loading = ui.label("Se încarcă...").classes("text-gray-400")
                            preview_container = ui.column().classes("w-full")

                            def load_preview():
                                loading.set_text("")
                                try:
                                    if feed["source_type"] == "scraper":
                                        _preview_scraper(feed, preview_container)
                                    else:
                                        _preview_rss(feed, preview_container)
                                except Exception as ex:
                                    with preview_container:
                                        ui.label(f"Eroare: {ex}").classes("text-red-500")

                            ui.timer(0.1, load_preview, once=True)
                        dlg.open()

                    tbl.on("delete", handle_delete)
                    tbl.on("preview", handle_preview)

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

from nicegui import ui
from ui.layout import navbar
from core.rss_parser import validate_feed, fetch_feed
from core.db import Session, Feed


def _load_feeds():
    with Session() as s:
        rows = s.query(Feed).filter_by(source_type="rss").order_by(Feed.created_at.desc()).all()
        return [
            {
                "id": f.id,
                "name": f.name,
                "url": f.url,
                "categories": f.categories or [],
                "poll_interval_minutes": f.poll_interval_minutes,
                "is_active": f.is_active,
                "last_checked_at": str(f.last_checked_at or "—"),
            }
            for f in rows
        ]


@ui.page("/feeds")
def feeds_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-8"):

        # ── Feed-uri active ───────────────────────────────────────────────
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("items-center gap-3"):
                ui.label("Feed-uri RSS active").classes("text-xl font-bold")
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
                        {"name": "name",      "label": "Nume",      "field": "name",      "align": "left"},
                        {"name": "url",       "label": "URL",       "field": "url",       "align": "left"},
                        {"name": "cats",      "label": "Categorii", "field": "cats",      "align": "left"},
                        {"name": "interval",  "label": "Interval",  "field": "poll_interval_minutes"},
                        {"name": "last",      "label": "Ultima verificare", "field": "last_checked_at"},
                        {"name": "active",    "label": "Activ",     "field": "is_active"},
                        {"name": "actions",   "label": "",          "field": "id"},
                    ]
                    rows = [
                        {
                            **f,
                            "cats": ", ".join(f["categories"]) if f["categories"] else "toate",
                        }
                        for f in feeds
                    ]

                    tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")

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
                        with ui.dialog() as dlg, ui.card().classes("w-full max-w-4xl"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(f"Preview: {feed['name']}").classes("text-lg font-bold")
                                ui.button(icon="close", on_click=dlg.close).props("flat dense round")
                            loading = ui.label("Se încarcă...").classes("text-gray-400")
                            preview_container = ui.column().classes("w-full")

                            def load_preview():
                                loading.set_text("")
                                try:
                                    items = fetch_feed(feed["url"])
                                    if not items:
                                        with preview_container:
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
                                    with preview_container:
                                        cols = [
                                            {"name": "title",    "label": "Titlu",    "field": "title",    "align": "left"},
                                            {"name": "category", "label": "Categorie","field": "category"},
                                            {"name": "published","label": "Data",     "field": "published"},
                                        ]
                                        ui.table(columns=cols, rows=rows, row_key="title", pagination=20).classes("w-full")
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

from nicegui import ui
from ui.layout import navbar
from core.rss_parser import validate_feed, fetch_feed
from core.cardigann import search as cardigann_search
from core.indexer_sync import sync_indexers, list_indexers_meta
from core.db import Session, Feed


def _load_feeds():
    with Session() as s:
        rows = s.query(Feed).order_by(Feed.created_at.desc()).all()
        return [
            {
                "id": f.id, "name": f.name, "url": f.url,
                "source_type": f.source_type, "indexer_id": f.indexer_id,
                "categories": f.categories or [],
                "poll_interval_minutes": f.poll_interval_minutes, "is_active": f.is_active,
            }
            for f in rows
        ]


@ui.page("/feeds")
def feeds_page():
    navbar()

    all_meta = {"data": list_indexers_meta()}

    with ui.column().classes("w-full p-6 gap-8"):

        # ── 1. Feed-uri active ──────────────────────────────────────────
        with ui.column().classes("w-full gap-2"):
            ui.label("Feed-uri active").classes("text-xl font-bold")
            list_container = ui.column().classes("w-full gap-2")

            def refresh_list():
                list_container.clear()
                feeds = _load_feeds()
                if not feeds:
                    with list_container:
                        ui.label("Niciun feed adăugat încă.").classes("text-gray-400 text-sm")
                    return
                with list_container:
                    columns = [
                        {"name": "name",       "label": "Nume",       "field": "name",       "align": "left"},
                        {"name": "type",       "label": "Tip",        "field": "source_type"},
                        {"name": "source",     "label": "Sursă",      "field": "source",     "align": "left"},
                        {"name": "categories", "label": "Categorii",  "field": "cats",       "align": "left"},
                        {"name": "interval",   "label": "Interval",   "field": "poll_interval_minutes"},
                        {"name": "active",     "label": "Activ",      "field": "is_active"},
                        {"name": "actions",    "label": "",           "field": "id"},
                    ]
                    rows = []
                    for f in feeds:
                        rows.append({
                            **f,
                            "source": f["indexer_id"] if f["source_type"] == "cardigann" else f["url"],
                            "cats": ", ".join(f["categories"]) if f.get("categories") else "toate",
                        })

                    table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
                    table.add_slot("body-cell-active", """
                        <q-td :props="props">
                            <q-badge :color="props.value ? 'green' : 'red'">
                                {{ props.value ? 'activ' : 'oprit' }}
                            </q-badge>
                        </q-td>
                    """)
                    table.add_slot("body-cell-actions", """
                        <q-td :props="props">
                            <q-btn flat dense icon="visibility" color="primary"
                                @click="$parent.$emit('preview', props.row)" />
                            <q-btn flat dense icon="delete" color="red"
                                @click="$parent.$emit('delete', props.row)" />
                        </q-td>
                    """)

                    def handle_delete(e):
                        fid = e.args["id"]
                        with Session() as s:
                            row = s.query(Feed).filter_by(id=fid).first()
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
                                    if feed["source_type"] == "rss":
                                        items = fetch_feed(feed["url"])
                                        rows = [
                                            {"title": i["title"], "category": i.get("category",""), "published": i.get("published",""), "link": i.get("link","")}
                                            for i in items[:50]
                                        ]
                                    else:
                                        items = cardigann_search(feed["indexer_id"], "")
                                        rows = [
                                            {"title": i.get("title",""), "category": i.get("category",""), "published": i.get("date",""), "link": i.get("magnet","")}
                                            for i in items[:50]
                                        ]
                                    if not rows:
                                        preview_container.clear()
                                        with preview_container:
                                            ui.label("Niciun item găsit.").classes("text-gray-400")
                                        return
                                    with preview_container:
                                        cols = [
                                            {"name": "title",     "label": "Titlu",     "field": "title",     "align": "left"},
                                            {"name": "category",  "label": "Categorie", "field": "category"},
                                            {"name": "published", "label": "Data",      "field": "published"},
                                        ]
                                        ui.table(columns=cols, rows=rows, row_key="title", pagination=20).classes("w-full")
                                except Exception as ex:
                                    with preview_container:
                                        ui.label(f"Eroare: {ex}").classes("text-red-500")

                            ui.timer(0.1, load_preview, once=True)
                        dlg.open()

                    table.on("delete", handle_delete)
                    table.on("preview", handle_preview)

            refresh_list()

        ui.separator()

        # ── 2. Adaugă RSS direct ────────────────────────────────────────
        with ui.column().classes("w-full gap-2"):
            ui.label("Adaugă RSS direct").classes("text-xl font-bold")
            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-end gap-3 flex-wrap"):
                    url_input = ui.input("URL Feed RSS").classes("flex-1 min-w-64")
                    name_input = ui.input("Nume prietenos").classes("flex-1 min-w-48")
                    interval_input = ui.number("Interval (min)", value=60, min=5).classes("w-32")
                    validate_btn = ui.button("Validează", on_click=lambda: on_validate()).props("outline")
                    ui.button("Salvează", on_click=lambda: on_save_rss())

                validate_status = ui.label("").classes("text-sm text-gray-500")
                categories_section = ui.column().classes("w-full gap-1 hidden")
                selected_cats: dict = {"checkboxes": {}}

                def on_validate():
                    validate_status.set_text("Se verifică...")
                    validate_status.classes(replace="text-sm text-gray-500")
                    categories_section.classes(add="hidden")
                    categories_section.clear()
                    selected_cats["checkboxes"] = {}
                    ok, msg = validate_feed(url_input.value)
                    if not ok:
                        validate_status.set_text(f"✘ {msg}")
                        validate_status.classes(replace="text-sm text-red-600")
                        return
                    validate_status.set_text(f"✔ {msg}")
                    validate_status.classes(replace="text-sm text-green-600")
                    items = fetch_feed(url_input.value)
                    cats = sorted(set(i["category"] for i in items if i.get("category")))
                    if cats:
                        categories_section.classes(remove="hidden")
                        with categories_section:
                            ui.label("Filtrează categorii (gol = toate):").classes("text-xs text-gray-400")
                            with ui.row().classes("flex-wrap gap-3"):
                                for cat in cats:
                                    cb = ui.checkbox(cat)
                                    selected_cats["checkboxes"][cat] = cb
                    else:
                        categories_section.classes(remove="hidden")
                        with categories_section:
                            ui.label("Nicio categorie detectată — se indexează tot feed-ul.").classes("text-xs text-gray-400")

                def on_save_rss():
                    if not url_input.value or not name_input.value:
                        ui.notify("Completează URL și nume", type="warning")
                        return
                    cats = [cat for cat, cb in selected_cats["checkboxes"].items() if cb.value]
                    with Session() as s:
                        s.add(Feed(
                            name=name_input.value, url=url_input.value,
                            source_type="rss", poll_interval_minutes=int(interval_input.value),
                            categories=cats if cats else None,
                            is_active=True,
                        ))
                        s.commit()
                    url_input.set_value("")
                    name_input.set_value("")
                    validate_status.set_text("")
                    categories_section.classes(add="hidden")
                    selected_cats["checkboxes"] = {}
                    ui.notify("Feed adăugat", type="positive")
                    refresh_list()

        ui.separator()

        # ── 3. Catalog Cardigann ────────────────────────────────────────
        with ui.column().classes("w-full gap-3"):
            with ui.row().classes("w-full items-center justify-between flex-wrap gap-3"):
                ui.label("Catalog Indexeri Cardigann").classes("text-xl font-bold")
                with ui.row().classes("items-center gap-2"):
                    sync_label = ui.label(f"{len(all_meta['data'])} indexeri").classes("text-xs text-gray-400")
                    def do_sync():
                        sync_label.set_text("Se sincronizează...")
                        count, msg = sync_indexers()
                        all_meta["data"] = list_indexers_meta()
                        sync_label.set_text(msg)
                        apply_filters()
                    ui.button("Sincronizează", icon="sync", on_click=do_sync).props("outline dense")

            # Filtre
            with ui.row().classes("w-full gap-3 flex-wrap items-center"):
                search_input = ui.input(placeholder="Caută după nume...").props("dense outlined clearable").classes("flex-1 min-w-48")
                all_types = ["toate"] + sorted(set(m["type"] for m in all_meta["data"] if m["type"]))
                type_select = ui.select(all_types, value="toate", label="Tip").props("dense outlined").classes("w-40")
                all_cats = ["toate"] + sorted(set(c for m in all_meta["data"] for c in m["categories"]))
                cat_select = ui.select(all_cats, value="toate", label="Categorie").props("dense outlined").classes("w-44")

            # Tabel catalog
            catalog_container = ui.element("div").classes("w-full")

            def apply_filters():
                catalog_container.clear()
                s = search_input.value.lower() if search_input.value else ""
                t = type_select.value
                c = cat_select.value
                filtered = [
                    m for m in all_meta["data"]
                    if (not s or s in m["name"].lower() or s in m["id"].lower())
                    and (t == "toate" or m["type"] == t)
                    and (c == "toate" or c in m["categories"])
                ]
                with catalog_container:
                    columns = [
                        {"name": "name",       "label": "Nume",       "field": "name",       "align": "left", "sortable": True},
                        {"name": "type",       "label": "Tip",        "field": "type",       "sortable": True},
                        {"name": "language",   "label": "Limbă",      "field": "language"},
                        {"name": "categories", "label": "Categorii",  "field": "cats",       "align": "left"},
                        {"name": "actions",    "label": "",           "field": "id"},
                    ]
                    rows = [
                        {**m, "cats": ", ".join(m["categories"][:5])}
                        for m in filtered
                    ]
                    tbl = ui.table(columns=columns, rows=rows, row_key="id", pagination=20).classes("w-full")
                    tbl.add_slot("body-cell-type", """
                        <q-td :props="props">
                            <q-badge :color="props.value === 'public' ? 'green' : props.value === 'private' ? 'red' : 'orange'">
                                {{ props.value }}
                            </q-badge>
                        </q-td>
                    """)
                    tbl.add_slot("body-cell-actions", """
                        <q-td :props="props">
                            <q-btn flat dense label="+ Adaugă" color="primary"
                                @click="$parent.$emit('add', props.row)" />
                        </q-td>
                    """)

                    def handle_add(e):
                        meta = e.args
                        with ui.dialog() as dlg, ui.card().classes("p-4 gap-3 min-w-96"):
                            ui.label(f"Adaugă: {meta['name']}").classes("font-bold text-lg")
                            name_in = ui.input("Nume prietenos", value=meta["name"]).classes("w-full")
                            intv = ui.number("Interval (minute)", value=60, min=5).classes("w-full")

                            cat_checks: dict = {}
                            meta_cats = meta.get("categories", [])
                            if meta_cats:
                                ui.label("Filtrează categorii (gol = toate):").classes("text-xs text-gray-400 mt-2")
                                with ui.row().classes("flex-wrap gap-3"):
                                    for cat in meta_cats:
                                        cb = ui.checkbox(cat)
                                        cat_checks[cat] = cb

                            with ui.row().classes("justify-end gap-2 mt-2"):
                                ui.button("Anulează", on_click=dlg.close).props("flat")
                                def confirm(m=meta, ni=name_in, iv=intv, cc=cat_checks):
                                    cats = [c for c, cb in cc.items() if cb.value]
                                    with Session() as sess:
                                        sess.add(Feed(
                                            name=ni.value, url="",
                                            source_type="cardigann",
                                            indexer_id=m["id"],
                                            poll_interval_minutes=int(iv.value),
                                            categories=cats if cats else None,
                                            is_active=True,
                                        ))
                                        sess.commit()
                                    dlg.close()
                                    ui.notify(f"{m['name']} adăugat", type="positive")
                                    refresh_list()
                                ui.button("Adaugă", on_click=confirm)
                        dlg.open()

                    tbl.on("add", handle_add)

            search_input.on_value_change(lambda _: apply_filters())
            type_select.on_value_change(lambda _: apply_filters())
            cat_select.on_value_change(lambda _: apply_filters())
            apply_filters()

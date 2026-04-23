from nicegui import ui
from ui.layout import navbar
from core.rss_parser import validate_feed, fetch_feed
from core.indexer_sync import sync_indexers, list_indexers_meta
from core.db import Session, Feed


def _load_feeds():
    with Session() as s:
        rows = s.query(Feed).order_by(Feed.created_at.desc()).all()
        return [
            {
                "id": f.id, "name": f.name, "url": f.url,
                "source_type": f.source_type, "indexer_id": f.indexer_id,
                "poll_interval_minutes": f.poll_interval_minutes, "is_active": f.is_active,
            }
            for f in rows
        ]


@ui.page("/feeds")
def feeds_page():
    navbar()

    # state catalog
    all_meta = {"data": list_indexers_meta()}
    filters = {"search": "", "type": "toate", "category": "toate"}

    with ui.column().classes("w-full p-6 gap-6"):
        ui.label("RSS Feeds").classes("text-2xl font-bold")

        with ui.tabs().classes("w-full") as tabs:
            tab_rss = ui.tab("RSS Direct")
            tab_cardigann = ui.tab(f"Cardigann / Indexer ({len(all_meta['data'])})")

        with ui.tab_panels(tabs, value=tab_rss).classes("w-full"):

            # ── RSS Direct ──────────────────────────────────────────────
            with ui.tab_panel(tab_rss):
                with ui.card().classes("w-full max-w-2xl"):
                    url_input = ui.input("URL Feed RSS").classes("w-full")
                    validate_status = ui.label("").classes("text-sm text-gray-500")
                    categories_row = ui.row().classes("flex-wrap gap-2 hidden")
                    selected_category = {"value": ""}
                    name_input = ui.input("Nume prietenos").classes("w-full")
                    interval_input = ui.number("Interval verificare (minute)", value=60, min=5, max=1440).classes("w-full")

                    def on_validate():
                        validate_status.set_text("Se verifică...")
                        validate_status.classes(replace="text-sm text-gray-500")
                        categories_row.classes(add="hidden")
                        categories_row.clear()
                        selected_category["value"] = ""
                        ok, msg = validate_feed(url_input.value)
                        if not ok:
                            validate_status.set_text(f"✘ {msg}")
                            validate_status.classes(replace="text-sm text-red-600")
                            return
                        validate_status.set_text(f"✔ {msg}")
                        validate_status.classes(replace="text-sm text-green-600")
                        items = fetch_feed(url_input.value)
                        cats = sorted(set(i["category"] for i in items if i.get("category")))
                        categories_row.classes(remove="hidden")
                        with categories_row:
                            if cats:
                                ui.label("Categorii detectate:").classes("text-xs text-gray-500 w-full")
                                for cat in cats:
                                    btn = ui.button(cat).props("outline dense")
                                    def make_select(c, b):
                                        def select():
                                            selected_category["value"] = c
                                            ui.notify(f"Categorie selectată: {c}")
                                        return select
                                    btn.on_click(make_select(cat, btn))
                            else:
                                ui.label("Nicio categorie — se indexează tot feed-ul.").classes("text-xs text-gray-400")

                    def on_save_rss():
                        if not url_input.value or not name_input.value:
                            ui.notify("Completează URL și nume", type="warning")
                            return
                        with Session() as s:
                            s.add(Feed(
                                name=name_input.value, url=url_input.value,
                                source_type="rss", poll_interval_minutes=int(interval_input.value),
                                is_active=True,
                            ))
                            s.commit()
                        url_input.set_value("")
                        name_input.set_value("")
                        validate_status.set_text("")
                        categories_row.classes(add="hidden")
                        ui.notify("Feed adăugat", type="positive")
                        refresh_list()

                    with ui.row().classes("gap-2 mt-2"):
                        ui.button("Validează", on_click=on_validate).props("outline")
                        ui.button("Salvează", on_click=on_save_rss)

            # ── Cardigann ───────────────────────────────────────────────
            with ui.tab_panel(tab_cardigann):

                # Bara filtre + sync
                with ui.row().classes("w-full items-center gap-3 flex-wrap"):
                    search_input = ui.input(placeholder="Caută indexer...").props("dense outlined").classes("flex-1 min-w-48")
                    all_types = ["toate"] + sorted(set(m["type"] for m in all_meta["data"] if m["type"]))
                    type_select = ui.select(all_types, value="toate", label="Tip").props("dense outlined").classes("w-36")
                    all_cats = ["toate"] + sorted(set(c for m in all_meta["data"] for c in m["categories"]))
                    cat_select = ui.select(all_cats, value="toate", label="Categorie").props("dense outlined").classes("w-40")

                    sync_label = ui.label("").classes("text-xs text-gray-400")

                    def do_sync():
                        sync_label.set_text("Se sincronizează...")
                        count, msg = sync_indexers()
                        all_meta["data"] = list_indexers_meta()
                        sync_label.set_text(msg)
                        apply_filters()

                    ui.button("Sincronizează", icon="sync", on_click=do_sync).props("outline dense")

                # Grid indexeri
                catalog = ui.grid(columns=3).classes("w-full mt-3 gap-3")
                cardigann_interval = {"value": 60}

                def apply_filters():
                    catalog.clear()
                    s = search_input.value.lower()
                    t = type_select.value
                    c = cat_select.value
                    filtered = [
                        m for m in all_meta["data"]
                        if (not s or s in m["name"].lower() or s in m["id"].lower())
                        and (t == "toate" or m["type"] == t)
                        and (c == "toate" or c in m["categories"])
                    ]
                    with catalog:
                        for meta in filtered[:150]:
                            with ui.card().classes("p-3 gap-1"):
                                ui.label(meta["name"]).classes("font-semibold text-sm")
                                type_color = {"public": "text-green-600", "private": "text-red-500", "semi-private": "text-yellow-600"}.get(meta["type"], "text-gray-400")
                                ui.label(f"{meta['type']} · {meta['language']}").classes(f"text-xs {type_color}")
                                if meta["categories"]:
                                    ui.label(", ".join(meta["categories"][:4])).classes("text-xs text-gray-400")

                                def make_add(m):
                                    def add():
                                        with ui.dialog() as dlg, ui.card():
                                            ui.label(f"Adaugă: {m['name']}").classes("font-bold")
                                            name_in = ui.input("Nume prietenos", value=m["name"]).classes("w-full")
                                            intv = ui.number("Interval (minute)", value=60, min=5).classes("w-full")
                                            with ui.row():
                                                ui.button("Anulează", on_click=dlg.close).props("flat")
                                                def confirm():
                                                    with Session() as sess:
                                                        sess.add(Feed(
                                                            name=name_in.value, url="",
                                                            source_type="cardigann",
                                                            indexer_id=m["id"],
                                                            poll_interval_minutes=int(intv.value),
                                                            is_active=True,
                                                        ))
                                                        sess.commit()
                                                    dlg.close()
                                                    ui.notify(f"{m['name']} adăugat", type="positive")
                                                    refresh_list()
                                                ui.button("Adaugă", on_click=confirm)
                                        dlg.open()
                                    return add

                                ui.button("+ Adaugă", on_click=make_add(meta)).props("flat dense").classes("mt-1")

                search_input.on_value_change(lambda _: apply_filters())
                type_select.on_value_change(lambda _: apply_filters())
                cat_select.on_value_change(lambda _: apply_filters())
                apply_filters()

        # ── Lista feeds active ──────────────────────────────────────────
        ui.separator()
        ui.label("Feed-uri active").classes("text-lg font-semibold")
        list_container = ui.column().classes("w-full gap-2")

        def refresh_list():
            list_container.clear()
            feeds = _load_feeds()
            if not feeds:
                with list_container:
                    ui.label("Niciun feed adăugat încă.").classes("text-gray-400 text-sm")
                return
            with list_container:
                for feed in feeds:
                    with ui.card().classes("w-full max-w-2xl"):
                        with ui.row().classes("w-full items-center justify-between"):
                            with ui.column().classes("gap-0"):
                                ui.label(feed["name"]).classes("font-semibold")
                                src = feed["indexer_id"] if feed["source_type"] == "cardigann" else feed["url"]
                                ui.label(f"{feed['source_type'].upper()} · {src}").classes("text-xs text-gray-400")
                                ui.label(f"Interval: {feed['poll_interval_minutes']} min").classes("text-xs text-gray-400")
                            with ui.row().classes("gap-2 items-center"):
                                toggle = ui.switch("", value=feed["is_active"])
                                def make_toggle(fid, sw):
                                    def t():
                                        with Session() as s:
                                            row = s.query(Feed).filter_by(id=fid).first()
                                            if row:
                                                row.is_active = sw.value
                                                s.commit()
                                    return t
                                toggle.on_value_change(make_toggle(feed["id"], toggle))

                                def make_delete(fid):
                                    def d():
                                        with Session() as s:
                                            row = s.query(Feed).filter_by(id=fid).first()
                                            if row:
                                                s.delete(row)
                                                s.commit()
                                        ui.notify("Feed șters", type="warning")
                                        refresh_list()
                                    return d
                                ui.button(icon="delete", on_click=make_delete(feed["id"])).props("flat dense color=red")

        refresh_list()

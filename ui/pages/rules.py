import re
from nicegui import ui
from ui.layout import navbar
from core.db import Session, Feed, Rule

RESOLUTIONS = ["Orice", "480p", "720p", "1080p", "4K"]
QUALITY_PRESETS = ["CAM", "HDCAM", "TS", "TELESYNC", "PDVD", "DVDSCR", "R5", "HC", "HARDCODED", "SCR", "HDTS"]


def _slugify(text: str) -> str:
    """Convert rule name to a folder-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def _load_feeds():
    with Session() as s:
        rows = s.query(Feed).filter_by(is_active=True).order_by(Feed.name).all()
        return [{"id": f.id, "name": f.name, "source_type": f.source_type} for f in rows]


def _load_rules():
    with Session() as s:
        rows = s.query(Rule).order_by(Rule.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "feed_ids": r.feed_ids or [],
                "must_contain": r.must_contain or [],
                "must_not_contain": r.must_not_contain or [],
                "size_min_mb": r.size_min_mb,
                "size_max_gb": r.size_max_gb,
                "seeders_min": r.seeders_min,
                "quality_banned": r.quality_banned or [],
                "resolution_min": r.resolution_min or "Orice",
                "languages": r.languages or [],
                "title_blacklist": r.title_blacklist or [],
                "download_subdir": r.download_subdir or "",
                "is_active": bool(r.is_active),
            }
            for r in rows
        ]


def _chip_input(container_ref: dict, item_list: list, placeholder: str,
                color: str = "primary", transform=None) -> ui.row:
    """
    Renders a tag/chip input row.
    container_ref['el'] holds the chip row element.
    Pressing space or enter adds a chip.
    """

    outer = ui.column().classes("gap-1 w-full")
    with outer:
        chip_row = ui.row().classes("flex-wrap gap-1 min-h-6")
        container_ref["el"] = chip_row

        def render():
            chip_row.clear()
            with chip_row:
                for item in item_list:
                    with ui.chip(
                        item, removable=True, color=color,
                        on_value_change=lambda e, v=item: (item_list.remove(v), render())
                    ):
                        pass

        inp = ui.input(placeholder=placeholder).props("dense").classes("w-40")

        def add_item(raw: str):
            val = raw.strip()
            if transform:
                val = transform(val)
            if val and val not in item_list:
                item_list.append(val)
                render()
            inp.set_value("")

        def on_keydown(e):
            key = e.args.get("key", "") if isinstance(e.args, dict) else ""
            val = inp.value or ""
            if key in (" ", "Enter") and val.strip():
                add_item(val)

        inp.on("keydown", on_keydown)
        inp.on("blur", lambda _: add_item(inp.value) if (inp.value or "").strip() else None)

        render()

    return outer


def _path_chip_input(path_segments: list) -> tuple:
    """
    Folder path as chips. Returns (outer_col, render_fn, get_path_fn).
    """
    outer = ui.column().classes("gap-1 w-full")
    with outer:
        ui.label("Folder descărcare (spațiu sau Enter = adaugă segment)").classes("text-xs text-gray-400")

        path_display = ui.row().classes("items-center gap-1 flex-wrap min-h-6")

        def render_path():
            path_display.clear()
            with path_display:
                for i, seg in enumerate(path_segments):
                    if i > 0:
                        ui.label("/").classes("text-gray-500 text-sm")
                    with ui.chip(
                        seg, removable=True, color="blue-grey",
                        on_value_change=lambda e, s=seg: (
                            path_segments.remove(s) if s in path_segments else None,
                            render_path()
                        )
                    ):
                        pass
                if not path_segments:
                    ui.label("(directorul implicit Transmission)").classes("text-xs text-gray-500 italic")

        path_inp = ui.input(placeholder="ex: filme").props("dense").classes("w-40")

        def add_segment(raw: str):
            val = raw.strip().strip("/").strip("\\")
            if val and val not in path_segments:
                path_segments.append(val)
                render_path()
            path_inp.set_value("")

        def on_path_key(e):
            key = e.args.get("key", "") if isinstance(e.args, dict) else ""
            val = path_inp.value or ""
            if key in (" ", "Enter") and val.strip():
                add_segment(val)

        path_inp.on("keydown", on_path_key)
        path_inp.on("blur", lambda _: add_segment(path_inp.value) if (path_inp.value or "").strip() else None)

        render_path()

    def get_path():
        return "/".join(path_segments) if path_segments else ""

    return outer, render_path, get_path, path_inp


def _rule_dialog(feeds: list[dict], existing: dict | None, on_save):
    r = existing or {}

    # Mutable state for lists (so closures capture by reference)
    must_contain    = list(r.get("must_contain", []))
    must_not_contain = list(r.get("must_not_contain", []))
    path_segments   = (r.get("download_subdir") or "").split("/") if r.get("download_subdir") else []
    banned_state    = {q: q in r.get("quality_banned", []) for q in QUALITY_PRESETS}
    res_state       = {"value": r.get("resolution_min", "Orice")}
    lang_list       = list(r.get("languages", []))
    bl_list         = list(r.get("title_blacklist", []))

    with ui.dialog() as dlg, ui.card().classes("w-full max-w-2xl gap-5 overflow-y-auto max-h-screen"):
        ui.label("Editează regulă" if existing else "Regulă nouă").classes("text-xl font-bold")

        # ── Nume + folder ────────────────────────────────────────────────
        with ui.column().classes("w-full gap-1"):
            ui.label("Nume regulă *").classes("text-xs text-gray-400")
            name_in = ui.input(placeholder="ex: Carti SF", value=r.get("name", "")).classes("w-full")

        _, render_path, get_path, path_inp = _path_chip_input(path_segments)

        def on_name_change(e):
            # Auto-fill first path segment from name if path is empty
            if not path_segments and name_in.value.strip():
                slug = _slugify(name_in.value)
                if slug:
                    path_segments.append(slug)
                    render_path()

        name_in.on("blur", on_name_change)

        # ── Filtre titlu ─────────────────────────────────────────────────
        with ui.card().classes("w-full gap-3 bg-gray-800"):
            ui.label("Filtrare titlu").classes("text-sm font-semibold")

            with ui.column().classes("w-full gap-1"):
                ui.label("Conține (toate trebuie să apară în titlu)").classes("text-xs text-green-400")
                _chip_input({"el": None}, must_contain, "ex: book", color="green",
                            transform=lambda v: v.lower())

            with ui.column().classes("w-full gap-1"):
                ui.label("Nu conține (niciuna nu trebuie să apară)").classes("text-xs text-red-400")
                _chip_input({"el": None}, must_not_contain, "ex: poetry", color="red",
                            transform=lambda v: v.lower())

            ui.label(
                "Gol = fără restricție pe titlu. "
                "Exemplu: [book] [english] + nu conține [poetry] → caută cărți în engleză fără poezie."
            ).classes("text-xs text-gray-500")

        # ── Feed-uri ────────────────────────────────────────────────────
        with ui.column().classes("w-full gap-1"):
            ui.label("Feed-uri (gol = toate feed-urile active)").classes("text-xs text-gray-400")
            feed_checks: dict[int, ui.checkbox] = {}
            if feeds:
                with ui.row().classes("flex-wrap gap-3"):
                    for f in feeds:
                        cb = ui.checkbox(f["name"], value=(f["id"] in r.get("feed_ids", [])))
                        feed_checks[f["id"]] = cb
            else:
                ui.label("Niciun feed activ.").classes("text-xs text-gray-500 italic")

        # ── Filtre per-regulă (opțional) ─────────────────────────────────
        with ui.expansion("Filtre per-regulă (opțional — suprascriu filtrul global)").classes("w-full"):
            ui.label("Câmpurile lăsate goale moștenesc filtrul global.").classes("text-xs text-gray-500 mb-2")

            with ui.row().classes("gap-6 flex-wrap"):
                with ui.column().classes("gap-1"):
                    ui.label("Dim. minimă (MB)").classes("text-xs text-gray-400")
                    size_min_in = ui.number(value=r.get("size_min_mb"), min=0,
                                            placeholder="global").classes("w-32")
                with ui.column().classes("gap-1"):
                    ui.label("Dim. maximă (GB)").classes("text-xs text-gray-400")
                    size_max_in = ui.number(value=r.get("size_max_gb"), min=0,
                                            placeholder="global").classes("w-32")
                with ui.column().classes("gap-1"):
                    ui.label("Seederi minim").classes("text-xs text-gray-400")
                    seeders_in = ui.number(value=r.get("seeders_min"), min=0,
                                           placeholder="global").classes("w-32")

            # Calități
            with ui.column().classes("w-full gap-1 mt-2"):
                ui.label("Calități interzise (override)").classes("text-xs text-gray-400")
                qual_btns: dict = {}
                with ui.row().classes("flex-wrap gap-2"):
                    for q in QUALITY_PRESETS:
                        btn = ui.button(q).props(f"dense color={'red' if banned_state[q] else 'grey'}")
                        def make_toggle(quality, button, state=banned_state):
                            def toggle():
                                state[quality] = not state[quality]
                                button.props(f"color={'red' if state[quality] else 'grey'}")
                            return toggle
                        btn.on_click(make_toggle(q, btn))
                        qual_btns[q] = btn

            # Rezoluție
            with ui.column().classes("w-full gap-1 mt-2"):
                ui.label("Rezoluție minimă (override)").classes("text-xs text-gray-400")
                res_btns: dict = {}
                with ui.row().classes("gap-2 flex-wrap"):
                    for res in RESOLUTIONS:
                        is_active = (res == res_state["value"])
                        btn = ui.button(res).props(f"dense {'color=primary' if is_active else 'outline'}")
                        def make_res(rv, b, rs=res_state):
                            def select():
                                rs["value"] = rv
                                for bb in res_btns.values():
                                    bb.props("outline")
                                b.props("dense color=primary")
                            return select
                        btn.on_click(make_res(res, btn))
                        res_btns[res] = btn

            # Limbi
            with ui.column().classes("w-full gap-1 mt-2"):
                ui.label("Limbi acceptate (override, gol = moștenește)").classes("text-xs text-gray-400")
                _chip_input({"el": None}, lang_list, "ex: en", color="blue-grey",
                            transform=lambda v: v.lower())

            # Blacklist titlu
            with ui.column().classes("w-full gap-1 mt-2"):
                ui.label("Blacklist cuvinte titlu (override)").classes("text-xs text-gray-400")
                _chip_input({"el": None}, bl_list, "ex: PROPER", color="red",
                            transform=lambda v: v.upper())

        # ── Butoane ──────────────────────────────────────────────────────
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Anulează", on_click=dlg.close).props("flat")

            def confirm():
                if not name_in.value.strip():
                    ui.notify("Numele este obligatoriu", type="warning")
                    return
                data = {
                    "name": name_in.value.strip(),
                    "feed_ids": [fid for fid, cb in feed_checks.items() if cb.value],
                    "must_contain": must_contain or None,
                    "must_not_contain": must_not_contain or None,
                    "size_min_mb": int(size_min_in.value) if size_min_in.value is not None else None,
                    "size_max_gb": int(size_max_in.value) if size_max_in.value is not None else None,
                    "seeders_min": int(seeders_in.value) if seeders_in.value is not None else None,
                    "quality_banned": [q for q, v in banned_state.items() if v] or None,
                    "resolution_min": res_state["value"] if res_state["value"] != "Orice" else None,
                    "languages": lang_list or None,
                    "title_blacklist": bl_list or None,
                    "download_subdir": get_path() or None,
                }
                dlg.close()
                on_save(data)

            ui.button("Salvează", on_click=confirm)

    dlg.open()


@ui.page("/rules")
def rules_page():
    navbar()

    with ui.column().classes("w-full p-6 gap-6 max-w-5xl"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Reguli de automatizare").classes("text-2xl font-bold")
            ui.button("+ Regulă nouă", on_click=lambda: open_add()).props("color=primary")

        ui.label(
            "O regulă monitorizează feed-urile selectate, potrivește titlurile "
            "și trimite automat la Transmission în folderul ales."
        ).classes("text-sm text-gray-400")

        rules_container = ui.column().classes("w-full gap-3")

        def refresh():
            rules_container.clear()
            all_rules = _load_rules()
            all_feeds = _load_feeds()
            feed_map = {f["id"]: f["name"] for f in all_feeds}

            if not all_rules:
                with rules_container:
                    ui.label("Nicio regulă definită.").classes("text-gray-400 text-sm")
                return

            with rules_container:
                columns = [
                    {"name": "name",       "label": "Nume",       "field": "name",        "align": "left", "sortable": True},
                    {"name": "match",      "label": "Conține",    "field": "match_label", "align": "left"},
                    {"name": "exclude",    "label": "Nu conține", "field": "excl_label",  "align": "left"},
                    {"name": "subdir",     "label": "Folder",     "field": "download_subdir"},
                    {"name": "feeds",      "label": "Feed-uri",   "field": "feeds_label", "align": "left"},
                    {"name": "active",     "label": "Activ",      "field": "is_active"},
                    {"name": "actions",    "label": "",           "field": "id"},
                ]
                rows = []
                for r in all_rules:
                    if r["feed_ids"]:
                        feeds_label = ", ".join(feed_map.get(fid, f"#{fid}") for fid in r["feed_ids"])
                    else:
                        feeds_label = "toate"
                    rows.append({
                        **r,
                        "match_label": ", ".join(r["must_contain"]) if r["must_contain"] else "—",
                        "excl_label":  ", ".join(r["must_not_contain"]) if r["must_not_contain"] else "—",
                        "feeds_label": feeds_label,
                    })

                tbl = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")

                tbl.add_slot("body-cell-match", """
                    <q-td :props="props">
                        <span v-if="props.value !== '—'" class="text-green-400 text-xs">{{ props.value }}</span>
                        <span v-else class="text-gray-500 text-xs">—</span>
                    </q-td>
                """)
                tbl.add_slot("body-cell-exclude", """
                    <q-td :props="props">
                        <span v-if="props.value !== '—'" class="text-red-400 text-xs">{{ props.value }}</span>
                        <span v-else class="text-gray-500 text-xs">—</span>
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
                        <q-btn flat dense :icon="props.row.is_active ? 'pause' : 'play_arrow'"
                            :color="props.row.is_active ? 'orange' : 'green'"
                            @click="$parent.$emit('toggle', props.row)" />
                        <q-btn flat dense icon="edit" color="primary"
                            @click="$parent.$emit('edit', props.row)" />
                        <q-btn flat dense icon="delete" color="red"
                            @click="$parent.$emit('delete', props.row)" />
                    </q-td>
                """)

                def handle_toggle(e):
                    with Session() as s:
                        row = s.query(Rule).filter_by(id=e.args["id"]).first()
                        if row:
                            row.is_active = not row.is_active
                            s.commit()
                    refresh()

                def handle_edit(e):
                    def save_edit(data):
                        with Session() as s:
                            row = s.query(Rule).filter_by(id=e.args["id"]).first()
                            if row:
                                for k, v in data.items():
                                    setattr(row, k, v)
                                s.commit()
                        ui.notify("Regulă actualizată", type="positive")
                        refresh()
                    _rule_dialog(_load_feeds(), e.args, save_edit)

                def handle_delete(e):
                    with Session() as s:
                        row = s.query(Rule).filter_by(id=e.args["id"]).first()
                        if row:
                            s.delete(row)
                            s.commit()
                    ui.notify(f"Regulă '{e.args.get('name','')}' ștearsă", type="warning")
                    refresh()

                tbl.on("toggle", handle_toggle)
                tbl.on("edit", handle_edit)
                tbl.on("delete", handle_delete)

        def open_add():
            def save_new(data):
                with Session() as s:
                    s.add(Rule(**data))
                    s.commit()
                ui.notify(f"Regulă '{data['name']}' creată", type="positive")
                refresh()
            _rule_dialog(_load_feeds(), None, save_new)

        refresh()

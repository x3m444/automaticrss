import json
from nicegui import ui
from ui.layout import navbar
from core.db import Session, Setting

FILTERS_KEY = "global_filters"

DEFAULTS = {
    "size_min_mb": 50,
    "size_max_gb": 50,
    "seeders_min": 1,
    "quality_banned": ["CAM", "HDCAM", "TS", "TELESYNC", "PDVD", "DVDSCR", "R5", "HC", "HARDCODED"],
    "resolution_min": "480p",
    "languages": [],
    "title_blacklist": [],
}

RESOLUTIONS = ["Orice", "480p", "720p", "1080p", "4K"]
QUALITY_PRESETS = ["CAM", "HDCAM", "TS", "TELESYNC", "PDVD", "DVDSCR", "R5", "HC", "HARDCODED", "SCR", "HDTS"]


def load_filters() -> dict:
    with Session() as s:
        row = s.query(Setting).filter_by(key=FILTERS_KEY).first()
        if row and row.value:
            return {**DEFAULTS, **json.loads(row.value)}
    return dict(DEFAULTS)


def save_filters(data: dict):
    with Session() as s:
        row = s.query(Setting).filter_by(key=FILTERS_KEY).first()
        if row:
            row.value = json.dumps(data)
        else:
            s.add(Setting(key=FILTERS_KEY, value=json.dumps(data)))
        s.commit()


@ui.page("/filters")
def filters_page():
    navbar()
    state = load_filters()

    with ui.column().classes("w-full p-6 gap-8 max-w-3xl"):
        ui.label("Filtre Globale").classes("text-2xl font-bold")
        ui.label("Se aplică automat tuturor regulilor și descărcărilor.").classes("text-sm text-gray-400")

        # ── Dimensiuni ──────────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            ui.label("Dimensiune fișier").classes("text-lg font-semibold")

            with ui.column().classes("gap-2"):
                ui.label("Minim").classes("text-sm text-gray-400")
                size_min = ui.number(value=state["size_min_mb"], min=0, suffix="MB").classes("w-40")
                with ui.row().classes("gap-2 flex-wrap"):
                    for preset in [10, 50, 100, 500]:
                        def set_min(v=preset):
                            size_min.set_value(v)
                        ui.button(f"{preset} MB", on_click=set_min).props("outline dense")

            with ui.column().classes("gap-2"):
                ui.label("Maxim").classes("text-sm text-gray-400")
                size_max = ui.number(value=state["size_max_gb"], min=0, suffix="GB").classes("w-40")
                with ui.row().classes("gap-2 flex-wrap"):
                    for preset in [5, 10, 20, 50]:
                        def set_max(v=preset):
                            size_max.set_value(v)
                        ui.button(f"{preset} GB", on_click=set_max).props("outline dense")

        # ── Seederi ─────────────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            ui.label("Seederi minim").classes("text-lg font-semibold")
            seeders = ui.number(value=state["seeders_min"], min=0).classes("w-40")
            with ui.row().classes("gap-2 flex-wrap"):
                for preset in [1, 3, 5, 10]:
                    def set_seed(v=preset):
                        seeders.set_value(v)
                    ui.button(str(preset), on_click=set_seed).props("outline dense")

        # ── Calități interzise ──────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            ui.label("Calități interzise").classes("text-lg font-semibold")
            ui.label("Roșu = blocat, gri = permis. Click pentru a comuta.").classes("text-xs text-gray-400")

            banned_state = {q: q in state["quality_banned"] for q in QUALITY_PRESETS}
            banned_buttons: dict = {}

            with ui.row().classes("flex-wrap gap-2"):
                for q in QUALITY_PRESETS:
                    color = "red" if banned_state[q] else "grey"
                    btn = ui.button(q).props(f"dense color={color}")

                    def make_toggle(quality, button):
                        def toggle():
                            banned_state[quality] = not banned_state[quality]
                            button.props(f"color={'red' if banned_state[quality] else 'grey'}")
                        return toggle

                    btn.on_click(make_toggle(q, btn))
                    banned_buttons[q] = btn

        # ── Rezoluție minimă ────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            ui.label("Rezoluție minimă acceptată").classes("text-lg font-semibold")
            res_state = {"value": state["resolution_min"]}
            res_buttons: dict = {}

            with ui.row().classes("gap-2 flex-wrap"):
                for res in RESOLUTIONS:
                    is_active = (res == state["resolution_min"])
                    btn = ui.button(res).props(f"dense {'color=primary' if is_active else 'outline'}")

                    def make_res(r, b):
                        def select():
                            res_state["value"] = r
                            for rb in res_buttons.values():
                                rb.props("outline")
                            b.props("dense color=primary")
                        return select

                    btn.on_click(make_res(res, btn))
                    res_buttons[res] = btn

        # ── Limbă ───────────────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            ui.label("Limbi acceptate").classes("text-lg font-semibold")
            ui.label("Gol = orice limbă.").classes("text-xs text-gray-400")

            lang_list = list(state["languages"])
            lang_container = ui.row().classes("flex-wrap gap-2")
            lang_input = ui.input(placeholder="ex: en, ro, fr").classes("w-32")

            def render_langs():
                lang_container.clear()
                with lang_container:
                    for lang in lang_list:
                        with ui.row().classes("items-center gap-0"):
                            ui.badge(lang.upper()).classes("text-sm px-2")
                            def make_remove_lang(l=lang):
                                def remove():
                                    lang_list.remove(l)
                                    render_langs()
                                return remove
                            ui.button(icon="close", on_click=make_remove_lang()).props("flat dense round size=xs")

            def add_lang():
                val = lang_input.value.strip().lower()
                if val and val not in lang_list:
                    lang_list.append(val)
                    render_langs()
                lang_input.set_value("")

            lang_input.on("keydown.enter", add_lang)
            ui.button(icon="add", on_click=add_lang).props("flat dense round")
            render_langs()

        # ── Blacklist titlu ─────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            ui.label("Blacklist cuvinte din titlu").classes("text-lg font-semibold")
            ui.label("Orice torrent al cărui titlu conține aceste cuvinte va fi ignorat.").classes("text-xs text-gray-400")

            bl_list = list(state["title_blacklist"])
            bl_container = ui.row().classes("flex-wrap gap-2")
            bl_input = ui.input(placeholder="ex: PROPER, REPACK").classes("w-40")

            def render_bl():
                bl_container.clear()
                with bl_container:
                    for word in bl_list:
                        with ui.row().classes("items-center gap-0"):
                            ui.badge(word).classes("text-sm px-2 bg-red-800")
                            def make_remove_bl(w=word):
                                def remove():
                                    bl_list.remove(w)
                                    render_bl()
                                return remove
                            ui.button(icon="close", on_click=make_remove_bl()).props("flat dense round size=xs")

            def add_bl():
                val = bl_input.value.strip().upper()
                if val and val not in bl_list:
                    bl_list.append(val)
                    render_bl()
                bl_input.set_value("")

            bl_input.on("keydown.enter", add_bl)
            ui.button(icon="add", on_click=add_bl).props("flat dense round")
            render_bl()

        # ── Salvează ────────────────────────────────────────────────────
        def on_save():
            data = {
                "size_min_mb": int(size_min.value or 0),
                "size_max_gb": int(size_max.value or 0),
                "seeders_min": int(seeders.value or 0),
                "quality_banned": [q for q, banned in banned_state.items() if banned],
                "resolution_min": res_state["value"],
                "languages": lang_list,
                "title_blacklist": bl_list,
            }
            save_filters(data)
            ui.notify("Filtre salvate", type="positive")

        ui.button("Salvează filtrele", on_click=on_save, icon="save").classes("mt-2")

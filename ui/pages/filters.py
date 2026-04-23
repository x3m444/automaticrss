import json
import re
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


def _saved_badge(container):
    container.clear()
    with container:
        ui.badge("salvat ✓").classes("text-xs bg-green-700")


@ui.page("/filters")
def filters_page():
    navbar()
    state = load_filters()

    with ui.column().classes("w-full p-6 gap-6 max-w-3xl"):
        ui.label("Filtre Globale").classes("text-2xl font-bold")
        ui.label("Fiecare modificare se salvează automat.").classes("text-sm text-gray-400")

        # ── Dimensiuni ──────────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Dimensiune fișier").classes("text-lg font-semibold")
                size_status = ui.row()
                with size_status:
                    ui.label(f"Activ: {state['size_min_mb']} MB – {state['size_max_gb']} GB").classes("text-xs text-green-400")

            with ui.row().classes("gap-8 flex-wrap"):
                with ui.column().classes("gap-2"):
                    ui.label("Minim").classes("text-xs text-gray-400")
                    size_min = ui.number(value=state["size_min_mb"], min=0, suffix="MB").classes("w-36")
                    with ui.row().classes("gap-1 flex-wrap"):
                        for p in [10, 50, 100, 500]:
                            def set_min(v=p):
                                size_min.set_value(v)
                                _update_size()
                            ui.button(f"{p} MB", on_click=set_min).props("outline dense")

                with ui.column().classes("gap-2"):
                    ui.label("Maxim").classes("text-xs text-gray-400")
                    size_max = ui.number(value=state["size_max_gb"], min=0, suffix="GB").classes("w-36")
                    with ui.row().classes("gap-1 flex-wrap"):
                        for p in [5, 10, 20, 50]:
                            def set_max(v=p):
                                size_max.set_value(v)
                                _update_size()
                            ui.button(f"{p} GB", on_click=set_max).props("outline dense")

            def _update_size():
                state["size_min_mb"] = int(size_min.value or 0)
                state["size_max_gb"] = int(size_max.value or 0)
                save_filters(state)
                size_status.clear()
                with size_status:
                    ui.label(f"Activ: {state['size_min_mb']} MB – {state['size_max_gb']} GB").classes("text-xs text-green-400")

            size_min.on("blur", lambda _: _update_size())
            size_max.on("blur", lambda _: _update_size())

        # ── Seederi ─────────────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Seederi minim").classes("text-lg font-semibold")
                seed_status = ui.row()
                with seed_status:
                    ui.label(f"Activ: minim {state['seeders_min']} seederi").classes("text-xs text-green-400")

            seeders = ui.number(value=state["seeders_min"], min=0).classes("w-36")

            def _update_seed():
                state["seeders_min"] = int(seeders.value or 0)
                save_filters(state)
                seed_status.clear()
                with seed_status:
                    ui.label(f"Activ: minim {state['seeders_min']} seederi").classes("text-xs text-green-400")

            with ui.row().classes("gap-2"):
                for p in [1, 3, 5, 10]:
                    def set_seed(v=p):
                        seeders.set_value(v)
                        _update_seed()
                    ui.button(str(p), on_click=set_seed).props("outline dense")

            seeders.on("blur", lambda _: _update_seed())

        # ── Calități interzise ──────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Calități interzise").classes("text-lg font-semibold")
                qual_status = ui.row()

            ui.label("Roșu = blocat. Click pentru a comuta.").classes("text-xs text-gray-400")

            banned_state = {q: q in state["quality_banned"] for q in QUALITY_PRESETS}

            def _refresh_qual_status():
                qual_status.clear()
                banned = [q for q, v in banned_state.items() if v]
                with qual_status:
                    if banned:
                        ui.label(f"Activ: {', '.join(banned)}").classes("text-xs text-red-400")
                    else:
                        ui.label("Nicio calitate blocată").classes("text-xs text-gray-400")

            def _update_qual():
                state["quality_banned"] = [q for q, v in banned_state.items() if v]
                save_filters(state)
                _refresh_qual_status()

            with ui.row().classes("flex-wrap gap-2"):
                for q in QUALITY_PRESETS:
                    btn = ui.button(q).props(f"dense color={'red' if banned_state[q] else 'grey'}")
                    def make_toggle(quality, button):
                        def toggle():
                            banned_state[quality] = not banned_state[quality]
                            button.props(f"color={'red' if banned_state[quality] else 'grey'}")
                            _update_qual()
                        return toggle
                    btn.on_click(make_toggle(q, btn))

            _refresh_qual_status()

        # ── Rezoluție minimă ────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Rezoluție minimă").classes("text-lg font-semibold")
                res_status = ui.row()

            res_state = {"value": state["resolution_min"]}
            res_buttons: dict = {}

            def _refresh_res_status():
                res_status.clear()
                with res_status:
                    ui.label(f"Activ: {res_state['value']}").classes("text-xs text-green-400")

            with ui.row().classes("gap-2 flex-wrap"):
                for res in RESOLUTIONS:
                    is_active = (res == state["resolution_min"])
                    btn = ui.button(res).props(f"dense {'color=primary' if is_active else 'outline'}")
                    def make_res(r, b):
                        def select():
                            res_state["value"] = r
                            state["resolution_min"] = r
                            for rb in res_buttons.values():
                                rb.props("outline")
                            b.props("dense color=primary")
                            save_filters(state)
                            _refresh_res_status()
                        return select
                    btn.on_click(make_res(res, btn))
                    res_buttons[res] = btn

            _refresh_res_status()

        # ── Limbă ───────────────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Limbi acceptate").classes("text-lg font-semibold")
                lang_status = ui.row()

            ui.label("Gol = orice limbă.").classes("text-xs text-gray-400")
            lang_list = list(state["languages"])
            lang_container = ui.row().classes("flex-wrap gap-2 min-h-8")
            lang_input = ui.input(placeholder="ex: en, ro").classes("w-28")

            def _refresh_lang_status():
                lang_status.clear()
                with lang_status:
                    if lang_list:
                        ui.label(f"Activ: {', '.join(lang_list)}").classes("text-xs text-green-400")
                    else:
                        ui.label("Orice limbă").classes("text-xs text-gray-400")

            def render_langs():
                lang_container.clear()
                with lang_container:
                    for lang in lang_list:
                        with ui.chip(lang.upper(), removable=True, on_value_change=lambda e, l=lang: (lang_list.remove(l), render_langs(), _save_langs())):
                            pass
                _refresh_lang_status()

            def _save_langs():
                state["languages"] = lang_list
                save_filters(state)

            def add_lang():
                val = lang_input.value.strip().lower()
                if val and val not in lang_list:
                    lang_list.append(val)
                    render_langs()
                    _save_langs()
                lang_input.set_value("")

            with ui.row().classes("items-center gap-2"):
                lang_input.on("keydown.enter", add_lang)
                ui.button(icon="add", on_click=add_lang).props("flat dense round")

            render_langs()

        # ── Blacklist titlu ─────────────────────────────────────────────
        with ui.card().classes("w-full gap-3"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Blacklist cuvinte din titlu").classes("text-lg font-semibold")
                bl_status = ui.row()

            ui.label("Torrente cu aceste cuvinte în titlu vor fi ignorate.").classes("text-xs text-gray-400")
            bl_list = list(state["title_blacklist"])
            bl_container = ui.row().classes("flex-wrap gap-2 min-h-8")
            bl_input = ui.input(placeholder="ex: PROPER").classes("w-36")

            def _refresh_bl_status():
                bl_status.clear()
                with bl_status:
                    if bl_list:
                        ui.label(f"Activ: {len(bl_list)} cuvinte blocate").classes("text-xs text-red-400")
                    else:
                        ui.label("Niciun cuvânt blocat").classes("text-xs text-gray-400")

            def render_bl():
                bl_container.clear()
                with bl_container:
                    for word in bl_list:
                        with ui.chip(word, removable=True, color="red", on_value_change=lambda e, w=word: (bl_list.remove(w), render_bl(), _save_bl())):
                            pass
                _refresh_bl_status()

            def _save_bl():
                state["title_blacklist"] = bl_list
                save_filters(state)

            def add_bl():
                val = bl_input.value.strip().upper()
                if val and val not in bl_list:
                    bl_list.append(val)
                    render_bl()
                    _save_bl()
                bl_input.set_value("")

            with ui.row().classes("items-center gap-2"):
                bl_input.on("keydown.enter", add_bl)
                ui.button(icon="add", on_click=add_bl).props("flat dense round")

            render_bl()

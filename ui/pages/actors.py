from nicegui import ui, run
from ui.layout import navbar


@ui.page("/actors")
def actors_page():
    navbar()

    state: dict = {"result": None, "loading": False}

    with ui.column().classes("w-full p-6 gap-6"):
        ui.label("Căutare Actor / Actriță").classes("text-2xl font-bold")

        with ui.row().classes("w-full items-center gap-3 max-w-xl"):
            search_inp = ui.input(placeholder="ex: Mia Malkova, Johnny Sins…").classes("flex-1")
            search_btn = ui.button("Caută", icon="search").props("color=primary")

        status_lbl = ui.label("").classes("text-sm text-gray-400")
        results_col = ui.column().classes("w-full gap-4")

        async def do_search(_=None):
            query = search_inp.value.strip()
            if not query:
                return
            state["loading"] = True
            search_btn.props("loading")
            status_lbl.set_text("Se caută…")
            results_col.clear()

            def _fetch():
                from core.scrapers.iafd import search_performer
                return search_performer(query)

            result = await run.io_bound(_fetch)
            state["result"] = result
            state["loading"] = False
            search_btn.props(remove="loading")

            if not result:
                status_lbl.set_text("Niciun rezultat găsit.")
                return

            status_lbl.set_text(
                f"{len(result['movies'])} filme găsite pentru {result['name']}"
            )
            _render_result(results_col, result)

        search_inp.on("keydown.enter", do_search)
        search_btn.on("click", do_search)


def _render_result(container, result: dict):
    with container:
        # ── Card performer ───────────────────────────────────────────────
        with ui.card().classes("w-full max-w-3xl"):
            with ui.row().classes("items-center gap-4"):
                if result.get("photo_url"):
                    ui.image(result["photo_url"]).classes("w-24 h-24 rounded-full object-cover")
                else:
                    ui.icon("person", size="4rem").classes("text-gray-400")
                with ui.column().classes("gap-1"):
                    ui.label(result["name"]).classes("text-xl font-bold")
                    ui.label(f"{len(result['movies'])} titluri în baza IAFD").classes("text-sm text-gray-400")
                    if result.get("iafd_url"):
                        ui.link("Vezi pe IAFD", result["iafd_url"], new_tab=True).classes("text-xs text-blue-400")

        # ── Lista filme ──────────────────────────────────────────────────
        with ui.card().classes("w-full max-w-3xl"):
            ui.label("Filmografie").classes("text-lg font-semibold mb-2")

            with ui.column().classes("w-full gap-1"):
                for movie in result["movies"]:
                    with ui.row().classes("w-full items-center gap-3 py-1"):
                        ui.label(movie["year"]).classes("text-xs text-gray-400 w-10 shrink-0")
                        ui.label(movie["title"]).classes("flex-1 text-sm")
                        ui.link("IAFD", movie["iafd_url"], new_tab=True).classes("text-xs text-gray-500")
                        ui.button(
                            "Caută",
                            on_click=lambda t=movie["title"]: ui.navigate.to(
                                f"/search?q={t.replace(' ', '+')}"
                            ),
                        ).props("outline dense size=sm")
                    ui.separator().classes("opacity-20")

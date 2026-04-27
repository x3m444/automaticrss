from nicegui import ui
from ui.auth import check_auth, _cfg


def navbar():
    check_auth()

    dark = ui.dark_mode()
    auth_enabled, _, _ = _cfg()

    with ui.header().classes("bg-gray-900 text-white"):
        with ui.row().classes("w-full items-center gap-6 px-4 py-2"):
            ui.label("AutomaticRSS").classes("text-xl font-bold tracking-wide")
            ui.link("Downloads", "/downloads").classes("text-white hover:text-gray-300")
            ui.link("Caută",     "/search").classes("text-white hover:text-gray-300")
            ui.link("Actori",    "/actors").classes("text-white hover:text-gray-300")
            ui.link("Watchlist", "/watchlist").classes("text-white hover:text-gray-300")
            ui.link("Feeds",     "/feeds").classes("text-white hover:text-gray-300")
            ui.link("Filtre",    "/filters").classes("text-white hover:text-gray-300")
            ui.link("Settings",  "/settings").classes("text-white hover:text-gray-300")

            ui.space()

            def toggle_dark():
                dark.toggle()
                icon_btn.props(f"icon={'light_mode' if dark.value else 'dark_mode'}")

            icon_btn = ui.button(icon="dark_mode", on_click=toggle_dark).props("flat dense round color=white")

            if auth_enabled:
                ui.button(icon="logout", on_click=lambda: ui.navigate.to("/logout")).props("flat dense round color=white").tooltip("Deconectare")

    dark.enable()

from nicegui import ui


def navbar():
    dark = ui.dark_mode()

    with ui.header().classes("bg-gray-900 text-white"):
        with ui.row().classes("w-full items-center gap-6 px-4 py-2"):
            ui.label("AutomaticRSS").classes("text-xl font-bold tracking-wide")
            ui.link("Downloads", "/downloads").classes("text-white hover:text-gray-300")
            ui.link("Caută",     "/search").classes("text-white hover:text-gray-300")
            ui.link("Watchlist", "/watchlist").classes("text-white hover:text-gray-300")
            ui.link("Feeds",     "/feeds").classes("text-white hover:text-gray-300")
            ui.link("Filtre",    "/filters").classes("text-white hover:text-gray-300")
            ui.link("Settings",  "/settings").classes("text-white hover:text-gray-300")

            ui.space()

            def toggle_dark():
                dark.toggle()
                icon_btn.props(f"icon={'light_mode' if dark.value else 'dark_mode'}")

            icon_btn = ui.button(icon="dark_mode", on_click=toggle_dark).props("flat dense round color=white")

    dark.enable()

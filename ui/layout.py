from nicegui import ui


def navbar():
    with ui.header().classes("bg-gray-800 text-white"):
        with ui.row().classes("w-full items-center gap-6 px-4"):
            ui.label("AutomaticRSS").classes("text-xl font-bold")
            ui.link("Feeds", "/feeds").classes("text-white hover:text-gray-300")
            ui.link("Downloads", "/downloads").classes("text-white hover:text-gray-300")
            ui.link("Settings", "/settings").classes("text-white hover:text-gray-300")

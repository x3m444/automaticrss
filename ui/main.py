from nicegui import ui
from ui.pages import feeds, downloads, settings


def start_ui():
    with ui.header():
        ui.label("AutomaticRSS").classes("text-xl font-bold")
        ui.link("Feeds", "/feeds")
        ui.link("Downloads", "/downloads")
        ui.link("Settings", "/settings")

    ui.run(title="AutomaticRSS", port=8080, reload=False)

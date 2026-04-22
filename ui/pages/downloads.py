from nicegui import ui
from ui.layout import navbar


@ui.page("/downloads")
def downloads_page():
    navbar()
    with ui.column().classes("w-full p-6 gap-4"):
        ui.label("Downloads").classes("text-2xl font-bold")
        ui.label("Monitorizare live Transmission — în curând.").classes("text-gray-500")

from nicegui import ui


@ui.page("/downloads")
def downloads_page():
    ui.label("Downloads").classes("text-2xl font-bold mb-4")
    ui.label("(în curând — monitorizare live Transmission)")

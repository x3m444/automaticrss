from nicegui import ui
from ui.layout import navbar


@ui.page("/settings")
def settings_page():
    navbar()
    with ui.column().classes("w-full p-6 gap-4"):
        ui.label("Setări").classes("text-2xl font-bold")

        with ui.card().classes("w-full max-w-xl"):
            ui.label("Transmission").classes("text-lg font-semibold mb-2")
            host = ui.input("Host", value="localhost").classes("w-full")
            port = ui.input("Port", value="9091").classes("w-full")
            user = ui.input("Username").classes("w-full")
            pwd = ui.input("Password", password=True).classes("w-full")

            def save():
                ui.notify("Salvat (DB în curând)", type="positive")

            ui.button("Salvează", on_click=save).classes("mt-2")

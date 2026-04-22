from nicegui import ui
from ui.layout import navbar
from core.rss_parser import validate_feed


@ui.page("/feeds")
def feeds_page():
    navbar()
    with ui.column().classes("w-full p-6 gap-4"):
        ui.label("RSS Feeds").classes("text-2xl font-bold")

        with ui.card().classes("w-full max-w-xl"):
            ui.label("Adaugă feed nou").classes("text-lg font-semibold mb-2")
            url_input = ui.input("URL Feed").classes("w-full")
            name_input = ui.input("Nume prietenos").classes("w-full")
            interval_input = ui.number("Interval verificare (minute)", value=60, min=5, max=1440)
            status_label = ui.label("").classes("text-sm text-gray-500")

            def on_validate():
                status_label.set_text("Se verifică...")
                valid, msg = validate_feed(url_input.value)
                color = "text-green-600" if valid else "text-red-600"
                status_label.classes(replace=f"text-sm {color}")
                status_label.set_text(f"{'✔' if valid else '✘'} {msg}")

            def on_save():
                ui.notify("Feed salvat (DB în curând)", type="positive")

            with ui.row().classes("gap-2 mt-2"):
                ui.button("Validează", on_click=on_validate).props("outline")
                ui.button("Salvează", on_click=on_save)

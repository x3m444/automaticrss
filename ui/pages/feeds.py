from nicegui import ui
from core.rss_parser import validate_feed


@ui.page("/feeds")
def feeds_page():
    ui.label("RSS Feeds").classes("text-2xl font-bold mb-4")

    with ui.card().classes("w-full"):
        ui.label("Adaugă feed nou")
        url_input = ui.input("URL Feed").classes("w-full")
        name_input = ui.input("Nume").classes("w-full")
        interval_input = ui.number("Interval (minute)", value=60, min=5)
        status_label = ui.label("")

        def on_validate():
            valid, msg = validate_feed(url_input.value)
            status_label.set_text(f"{'OK' if valid else 'Eroare'}: {msg}")

        def on_save():
            ui.notify("Feed salvat (TODO: persistenta DB)", type="positive")

        with ui.row():
            ui.button("Validează", on_click=on_validate)
            ui.button("Salvează", on_click=on_save)

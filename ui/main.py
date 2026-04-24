from nicegui import ui, app
from ui.pages import feeds, downloads, settings, filters, rules, watchlist


@ui.page("/")
def index():
    ui.navigate.to("/feeds")


def start_ui():
    ui.run(title="AutomaticRSS", port=8080, reload=False)

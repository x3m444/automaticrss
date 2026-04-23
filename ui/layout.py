from nicegui import ui
from core.db import Session, Setting


def _check_db() -> tuple[bool, str]:
    try:
        with Session() as s:
            s.execute(__import__("sqlalchemy").text("SELECT 1"))
        return True, "Supabase"
    except Exception as e:
        return False, f"Supabase: {e}"


def _check_transmission() -> tuple[bool, str]:
    try:
        from transmission_rpc import Client
        with Session() as s:
            def get(key, default):
                row = s.query(Setting).filter_by(key=key).first()
                return row.value if row else default
            host = get("transmission_host", "localhost")
            port = int(get("transmission_port", "9091"))
            user = get("transmission_user", "")
            pwd  = get("transmission_pass", "")
        c = Client(host=host, port=port, username=user, password=pwd)
        session = c.get_session()
        return True, f"Transmission {host}:{port} v{session.version}"
    except Exception:
        return False, "Transmission: offline"


def navbar():
    dark = ui.dark_mode()

    with ui.header().classes("bg-gray-900 text-white"):
        with ui.row().classes("w-full items-center gap-6 px-4 py-2"):
            ui.label("AutomaticRSS").classes("text-xl font-bold tracking-wide")
            ui.link("Feeds",     "/feeds").classes("text-white hover:text-gray-300")
            ui.link("Downloads", "/downloads").classes("text-white hover:text-gray-300")
            ui.link("Settings",  "/settings").classes("text-white hover:text-gray-300")

            ui.space()

            # Badge DB
            with ui.row().classes("items-center gap-1"):
                db_dot   = ui.icon("circle", size="xs").classes("text-gray-400")
                db_label = ui.label("DB...").classes("text-xs text-gray-300")

            ui.label("·").classes("text-gray-500")

            # Badge Transmission
            with ui.row().classes("items-center gap-1"):
                tr_dot   = ui.icon("circle", size="xs").classes("text-gray-400")
                tr_label = ui.label("Transmission...").classes("text-xs text-gray-300")

            ui.label("·").classes("text-gray-500")

            # Toggle dark/light
            def toggle_dark():
                dark.toggle()
                icon_btn.props(f"icon={'light_mode' if dark.value else 'dark_mode'}")

            icon_btn = ui.button(icon="dark_mode", on_click=toggle_dark).props("flat dense round color=white")

            def refresh():
                db_ok, db_msg = _check_db()
                db_dot.classes(replace="text-green-400" if db_ok else "text-red-400")
                db_label.set_text(db_msg)

                tr_ok, tr_msg = _check_transmission()
                tr_dot.classes(replace="text-green-400" if tr_ok else "text-red-400")
                tr_label.set_text(tr_msg)

            refresh()
            ui.timer(30, refresh)

    # dark mode activ implicit
    dark.enable()

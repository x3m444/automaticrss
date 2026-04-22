from nicegui import ui
from core.db import Session, Setting


@ui.page("/settings")
def settings_page():
    ui.label("Setări").classes("text-2xl font-bold mb-4")

    with Session() as s:
        def get(key, default=""):
            row = s.query(Setting).filter_by(key=key).first()
            return row.value if row else default

        with ui.card().classes("w-full"):
            ui.label("Transmission")
            host = ui.input("Host", value=get("transmission_host", "localhost"))
            port = ui.input("Port", value=get("transmission_port", "9091"))
            user = ui.input("User", value=get("transmission_user", ""))
            pwd = ui.input("Password", value=get("transmission_pass", ""), password=True)

            def save():
                for key, inp in [
                    ("transmission_host", host),
                    ("transmission_port", port),
                    ("transmission_user", user),
                    ("transmission_pass", pwd),
                ]:
                    row = s.query(Setting).filter_by(key=key).first()
                    if row:
                        row.value = inp.value
                    else:
                        s.add(Setting(key=key, value=inp.value))
                s.commit()
                ui.notify("Salvat", type="positive")

            ui.button("Salvează", on_click=save)

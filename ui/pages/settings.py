from nicegui import ui
from ui.layout import navbar
from core.db import Session, Setting


def _get(s, key, default=""):
    row = s.query(Setting).filter_by(key=key).first()
    return row.value if row else default


def _set(s, key, value):
    row = s.query(Setting).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        s.add(Setting(key=key, value=value))


@ui.page("/settings")
def settings_page():
    navbar()
    with ui.column().classes("w-full p-6 gap-4"):
        ui.label("Setări").classes("text-2xl font-bold")

        with ui.card().classes("w-full max-w-xl"):
            ui.label("Transmission").classes("text-lg font-semibold mb-2")

            with Session() as s:
                host_val = _get(s, "transmission_host", "localhost")
                port_val = _get(s, "transmission_port", "9091")
                user_val = _get(s, "transmission_user", "")
                pass_val = _get(s, "transmission_pass", "")

            host = ui.input("Host", value=host_val).classes("w-full")
            port = ui.input("Port", value=port_val).classes("w-full")
            user = ui.input("Username", value=user_val).classes("w-full")
            pwd = ui.input("Password", value=pass_val, password=True).classes("w-full")
            status = ui.label("").classes("text-sm mt-1")

            def save():
                with Session() as s:
                    for key, inp in [
                        ("transmission_host", host),
                        ("transmission_port", port),
                        ("transmission_user", user),
                        ("transmission_pass", pwd),
                    ]:
                        _set(s, key, inp.value)
                    s.commit()
                ui.notify("Salvat", type="positive")

            def test():
                status.set_text("Se testează...")
                status.classes(replace="text-sm mt-1 text-gray-500")
                try:
                    from transmission_rpc import Client
                    c = Client(
                        host=host.value,
                        port=int(port.value),
                        username=user.value,
                        password=pwd.value,
                    )
                    torrents = c.get_torrents()
                    status.set_text(f"✔ Conectat — {len(torrents)} torrent(e) active")
                    status.classes(replace="text-sm mt-1 text-green-600")
                except Exception as e:
                    status.set_text(f"✘ Eroare: {e}")
                    status.classes(replace="text-sm mt-1 text-red-600")

            with ui.row().classes("gap-2 mt-3"):
                ui.button("Salvează", on_click=save)
                ui.button("Testează conexiunea", on_click=test).props("outline")

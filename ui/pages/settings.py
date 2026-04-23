import os
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


def _test_write(path: str) -> tuple[bool, str]:
    try:
        os.makedirs(path, exist_ok=True)
        tmp = os.path.join(path, ".arss_write_test")
        with open(tmp, "w") as f:
            f.write("test")
        os.remove(tmp)
        return True, f"✔ Scriere permisă în: {path}"
    except PermissionError:
        return False, f"✘ Fără drepturi de scriere în: {path}"
    except Exception as e:
        return False, f"✘ Eroare: {e}"


@ui.page("/settings")
def settings_page():
    navbar()
    with ui.column().classes("w-full p-6 gap-6"):
        ui.label("Setări").classes("text-2xl font-bold")

        # ── Transmission ────────────────────────────────────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            ui.label("Transmission").classes("text-lg font-semibold")

            with Session() as s:
                host_val = _get(s, "transmission_host", "localhost")
                port_val = _get(s, "transmission_port", "9091")
                user_val = _get(s, "transmission_user", "")
                pass_val = _get(s, "transmission_pass", "")
                dir_val  = _get(s, "transmission_download_dir", "")

            host = ui.input("Host", value=host_val).classes("w-full")
            port = ui.input("Port", value=port_val).classes("w-full")
            user = ui.input("Username", value=user_val).classes("w-full")
            pwd  = ui.input("Password", value=pass_val, password=True).classes("w-full")

            ui.separator()

            ui.label("Director de descărcare").classes("text-sm font-medium text-gray-600")
            with ui.row().classes("w-full items-center gap-2"):
                download_dir = ui.input("Cale director", value=dir_val).classes("flex-1")
                ui.button("Test scriere", on_click=lambda: on_test_write()).props("outline dense")

            dir_status = ui.label("").classes("text-sm")

            conn_status = ui.label("").classes("text-sm mt-1")

            def on_test_write():
                path = download_dir.value.strip()
                if not path:
                    dir_status.set_text("✘ Introdu o cale")
                    dir_status.classes(replace="text-sm text-red-600")
                    return
                ok, msg = _test_write(path)
                dir_status.set_text(msg)
                dir_status.classes(replace=f"text-sm {'text-green-600' if ok else 'text-red-600'}")

            def save():
                with Session() as s:
                    for key, inp in [
                        ("transmission_host", host),
                        ("transmission_port", port),
                        ("transmission_user", user),
                        ("transmission_pass", pwd),
                        ("transmission_download_dir", download_dir),
                    ]:
                        _set(s, key, inp.value)
                    s.commit()
                ui.notify("Salvat", type="positive")

            def _connect():
                from transmission_rpc import Client
                return Client(
                    host=host.value, port=int(port.value),
                    username=user.value, password=pwd.value,
                )

            def _apply_session(session, torrents_count):
                download_dir.set_value(session.download_dir)
                dir_status.set_text("Director citit din Transmission — apasă Test scriere pentru a verifica.")
                dir_status.classes(replace="text-sm text-blue-500")
                conn_status.set_text(f"✔ Conectat — {host.value}:{port.value} · v{session.version} · {torrents_count} torrent(e)")
                conn_status.classes(replace="text-sm text-green-600")

            def test():
                conn_status.set_text("Se testează...")
                conn_status.classes(replace="text-sm text-gray-500")
                try:
                    c = _connect()
                    session = c.get_session()
                    _apply_session(session, len(c.get_torrents()))
                except Exception as e:
                    conn_status.set_text(f"✘ {e}")
                    conn_status.classes(replace="text-sm text-red-600")

            # auto-populare la încărcarea paginii
            if not dir_val:
                try:
                    c = _connect()
                    session = c.get_session()
                    _apply_session(session, len(c.get_torrents()))
                except Exception:
                    pass

            with ui.row().classes("gap-2 mt-3"):
                ui.button("Salvează", on_click=save)
                ui.button("Testează conexiunea", on_click=test).props("outline")

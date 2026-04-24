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
            # În Docker Compose hostul e "transmission" (numele serviciului), nu "localhost"
            _default_host = os.getenv("TRANSMISSION_HOST", "localhost")
            _default_port = os.getenv("TRANSMISSION_PORT", "9091")

            with Session() as s:
                host_val = _get(s, "transmission_host", _default_host)
                port_val = _get(s, "transmission_port", _default_port)
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

        # ── FlareSolverr ─────────────────────────────────────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("FlareSolverr").classes("text-lg font-semibold")
                ui.badge("opțional").props("outline color=grey")

            ui.label(
                "Dacă indexerii sunt protejați de Cloudflare, FlareSolverr rezolvă challenge-ul. "
                "Lasă gol dacă nu îl folosești."
            ).classes("text-xs text-gray-400")

            _default_fs = os.getenv("FLARESOLVERR_URL", "")
            with Session() as s:
                fs_url_val = _get(s, "flaresolverr_url", _default_fs)

            fs_url = ui.input("URL FlareSolverr", value=fs_url_val, placeholder="http://localhost:8191").classes("w-full")
            fs_status = ui.label("").classes("text-sm mt-1")

            def save_fs():
                with Session() as s:
                    _set(s, "flaresolverr_url", fs_url.value.rstrip("/"))
                    s.commit()
                ui.notify("FlareSolverr salvat", type="positive")

            def test_fs():
                import httpx as _httpx
                fs_status.set_text("Se testează...")
                fs_status.classes(replace="text-sm text-gray-500")
                try:
                    r = _httpx.get(f"{fs_url.value.rstrip('/')}/health", timeout=5)
                    if r.status_code == 200:
                        fs_status.set_text("✔ FlareSolverr online")
                        fs_status.classes(replace="text-sm text-green-600")
                    else:
                        fs_status.set_text(f"✘ HTTP {r.status_code}")
                        fs_status.classes(replace="text-sm text-red-600")
                except Exception as e:
                    fs_status.set_text(f"✘ {e}")
                    fs_status.classes(replace="text-sm text-red-600")

            with ui.row().classes("gap-2 mt-2"):
                ui.button("Salvează", on_click=save_fs)
                ui.button("Testează conexiunea", on_click=test_fs).props("outline")

        # ── Jackett ──────────────────────────────────────────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Jackett").classes("text-lg font-semibold")
                ui.badge("opțional").props("outline color=grey")

            ui.label(
                "Dacă Jackett rulează (local sau în Docker), îl poți folosi ca sursă "
                "alternativă pentru indexeri. API key-ul îl găsești în interfața Jackett."
            ).classes("text-xs text-gray-400")

            _default_jackett = os.getenv("JACKETT_URL", "http://localhost:9117")
            with Session() as s:
                jackett_url_val = _get(s, "jackett_url", _default_jackett)
                jackett_key_val = _get(s, "jackett_api_key", "")

            jackett_url = ui.input("URL Jackett", value=jackett_url_val).classes("w-full")
            jackett_key = ui.input("API Key", value=jackett_key_val).classes("w-full")

            jackett_status = ui.label("").classes("text-sm mt-1")

            def save_jackett():
                with Session() as s:
                    _set(s, "jackett_url", jackett_url.value.rstrip("/"))
                    _set(s, "jackett_api_key", jackett_key.value.strip())
                    s.commit()
                ui.notify("Jackett salvat", type="positive")

            def test_jackett():
                import httpx
                jackett_status.set_text("Se testează...")
                jackett_status.classes(replace="text-sm text-gray-500")
                try:
                    url = f"{jackett_url.value.rstrip('/')}/api/v2.0/server/config"
                    params = {"apikey": jackett_key.value.strip()}
                    r = httpx.get(url, params=params, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        version = data.get("version", "?")
                        jackett_status.set_text(f"✔ Jackett v{version} — conectat")
                        jackett_status.classes(replace="text-sm text-green-600")
                    else:
                        jackett_status.set_text(f"✘ HTTP {r.status_code} — verifică URL și API key")
                        jackett_status.classes(replace="text-sm text-red-600")
                except Exception as e:
                    jackett_status.set_text(f"✘ {e}")
                    jackett_status.classes(replace="text-sm text-red-600")

            with ui.row().classes("gap-2 mt-2"):
                ui.button("Salvează", on_click=save_jackett)
                ui.button("Testează conexiunea", on_click=test_jackett).props("outline")

import os
from nicegui import ui, run
from ui.layout import navbar
from core.db import Session, Setting, Instance
from core.config import INSTANCE_ID


def _get_setting(s, key, default=""):
    row = s.query(Setting).filter_by(key=key).first()
    return row.value if row else default


def _set_setting(s, key, value):
    row = s.query(Setting).filter_by(key=key).first()
    if row:
        row.value = value
    else:
        s.add(Setting(key=key, value=value))


def _get_instance(s) -> Instance | None:
    return s.query(Instance).filter_by(id=INSTANCE_ID).first()


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

        # ── Această mașină ───────────────────────────────────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Această mașină").classes("text-lg font-semibold")
                ui.badge(f"ID: {INSTANCE_ID[:8]}…", color="grey").props("outline")

            ui.label(
                "Setările de mai jos sunt locale — se aplică doar pe această mașină."
            ).classes("text-xs text-gray-400")

            with Session() as s:
                inst = _get_instance(s)
                inst_name = inst.name if inst else os.environ.get("COMPUTERNAME", "Default")
                tr_host   = inst.transmission_host if inst else "localhost"
                tr_port   = str(inst.transmission_port) if inst else "9091"
                tr_user   = inst.transmission_user if inst else ""
                tr_pass   = inst.transmission_pass if inst else ""
                tr_dir    = inst.download_dir if inst else ""

            name_inp = ui.input("Nume mașină", value=inst_name).classes("w-full")
            ui.separator()
            ui.label("Transmission").classes("text-sm font-medium text-gray-500")

            host = ui.input("Host", value=tr_host).classes("w-full")
            port = ui.input("Port", value=tr_port).classes("w-full")
            user = ui.input("Username", value=tr_user).classes("w-full")
            pwd  = ui.input("Password", value=tr_pass, password=True).classes("w-full")

            ui.separator()
            ui.label("Director de descărcare").classes("text-sm font-medium text-gray-500")
            with ui.row().classes("w-full items-center gap-2"):
                download_dir = ui.input("Cale director", value=tr_dir).classes("flex-1")
                ui.button("Test scriere", on_click=lambda: _on_test_write()).props("outline dense")

            dir_status  = ui.label("").classes("text-sm")
            conn_status = ui.label("").classes("text-sm mt-1")

            def _on_test_write():
                path = download_dir.value.strip()
                if not path:
                    dir_status.set_text("✘ Introdu o cale")
                    dir_status.classes(replace="text-sm text-red-600")
                    return
                ok, msg = _test_write(path)
                dir_status.set_text(msg)
                dir_status.classes(replace=f"text-sm {'text-green-600' if ok else 'text-red-600'}")

            def _connect():
                from transmission_rpc import Client
                return Client(
                    host=host.value, port=int(port.value or "9091"),
                    username=user.value, password=pwd.value,
                )

            def _apply_session(session, count):
                download_dir.set_value(session.download_dir)
                dir_status.set_text("Director citit din Transmission — apasă Test scriere pentru verificare.")
                dir_status.classes(replace="text-sm text-blue-500")
                conn_status.set_text(
                    f"✔ Conectat — {host.value}:{port.value} · v{session.version} · {count} torrent(e)"
                )
                conn_status.classes(replace="text-sm text-green-600")

            def save_instance():
                from datetime import datetime
                with Session() as s:
                    inst = _get_instance(s)
                    if inst:
                        inst.name              = name_inp.value.strip() or inst.name
                        inst.transmission_host = host.value.strip()
                        inst.transmission_port = int(port.value or "9091")
                        inst.transmission_user = user.value.strip()
                        inst.transmission_pass = pwd.value
                        inst.download_dir      = download_dir.value.strip() or None
                    else:
                        from core.instance import ensure_instance as _ei
                        _ei()
                        inst = _get_instance(s)
                        if inst:
                            inst.name              = name_inp.value.strip()
                            inst.transmission_host = host.value.strip()
                            inst.transmission_port = int(port.value or "9091")
                            inst.transmission_user = user.value.strip()
                            inst.transmission_pass = pwd.value
                            inst.download_dir      = download_dir.value.strip() or None
                    s.commit()
                ui.notify("✓ Salvat", type="positive")

            def test_connection():
                conn_status.set_text("Se testează...")
                conn_status.classes(replace="text-sm text-gray-500")
                try:
                    c = _connect()
                    session = c.get_session()
                    _apply_session(session, len(c.get_torrents()))
                except Exception as e:
                    conn_status.set_text(f"✘ {e}")
                    conn_status.classes(replace="text-sm text-red-600")

            with ui.row().classes("gap-2 mt-3"):
                ui.button("Salvează", on_click=save_instance).props("color=primary")
                ui.button("Testează conexiunea", on_click=test_connection).props("outline")

            if not tr_dir:
                async def _auto_populate():
                    try:
                        def _fetch():
                            c = _connect()
                            return c.get_session(), len(c.get_torrents())
                        session, count = await run.io_bound(_fetch)
                        _apply_session(session, count)
                    except Exception:
                        pass
                ui.timer(0.1, _auto_populate, once=True)

        # ── Disk Management ──────────────────────────────────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Disk Management").classes("text-lg font-semibold")
                ui.badge("per-mașină", color="grey").props("outline")

            ui.label(
                "Dacă spațiul liber scade sub pragul minim, se șterg automat torrentele "
                "completate (cele mai vechi primele) până se atinge spațiul țintă."
            ).classes("text-xs text-gray-400")

            with Session() as s:
                inst_dm = _get_instance(s)
                dm_enabled = inst_dm.disk_cleanup_enabled if inst_dm else False
                dm_min     = inst_dm.disk_min_free_gb    if inst_dm else 10
                dm_target  = inst_dm.disk_target_free_gb if inst_dm else 20

            dm_toggle = ui.switch("Activează curățare automată", value=dm_enabled)
            with ui.row().classes("w-full items-center gap-4"):
                dm_min_inp    = ui.number("Spațiu minim liber (GB)",  value=dm_min,    min=1, step=1).classes("flex-1")
                dm_target_inp = ui.number("Spațiu țintă eliberat (GB)", value=dm_target, min=1, step=1).classes("flex-1")

            disk_status = ui.label("").classes("text-sm mt-1")

            def save_disk():
                with Session() as s:
                    inst = _get_instance(s)
                    if inst:
                        inst.disk_cleanup_enabled = dm_toggle.value
                        inst.disk_min_free_gb     = int(dm_min_inp.value or 10)
                        inst.disk_target_free_gb  = int(dm_target_inp.value or 20)
                        s.commit()
                ui.notify("✓ Disk management salvat", type="positive")

            def check_now():
                import shutil
                path = ""
                with Session() as s:
                    inst = _get_instance(s)
                    if inst:
                        path = inst.download_dir or ""
                if not path:
                    disk_status.set_text("✘ Director de descărcare neconfigurat")
                    disk_status.classes(replace="text-sm text-red-600")
                    return
                try:
                    usage = shutil.disk_usage(path)
                    free_gb  = usage.free  / 1024**3
                    total_gb = usage.total / 1024**3
                    used_pct = (usage.used / usage.total) * 100
                    disk_status.set_text(
                        f"Liber: {free_gb:.1f} GB / {total_gb:.1f} GB  ({used_pct:.0f}% folosit)"
                    )
                    disk_status.classes(replace="text-sm text-green-600")
                except Exception as e:
                    disk_status.set_text(f"✘ {e}")
                    disk_status.classes(replace="text-sm text-red-600")

            with ui.row().classes("gap-2 mt-3"):
                ui.button("Salvează", on_click=save_disk).props("color=primary")
                ui.button("Verifică spațiu acum", on_click=check_now).props("outline")

        # ── Transmission — Limite ────────────────────────────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Transmission — Limite").classes("text-lg font-semibold")
                ui.badge("per-mașină", color="grey").props("outline")

            ui.label("Viteze în KB/s (0 = nelimitat). Coada limitează torrentele active simultan.") \
              .classes("text-xs text-gray-400")

            dl_enabled = ui.switch("Limitează download", value=False)
            with ui.row().classes("w-full items-center gap-4"):
                dl_limit = ui.number("Download (KB/s)", value=0, min=0, step=100).classes("flex-1")

            ui.separator()

            ul_enabled = ui.switch("Limitează upload", value=False)
            with ui.row().classes("w-full items-center gap-4"):
                ul_limit = ui.number("Upload (KB/s)", value=0, min=0, step=100).classes("flex-1")

            ui.separator()

            queue_enabled = ui.switch("Limitează coada de download", value=True)
            with ui.row().classes("w-full items-center gap-4"):
                queue_size = ui.number("Torrente simultane", value=5, min=1, step=1).classes("flex-1")

            tr_limits_status = ui.label("").classes("text-sm mt-1")

            def _load_tr_limits():
                try:
                    c = _connect()
                    sess = c.get_session()
                    dl_enabled.set_value(sess.speed_limit_down_enabled)
                    dl_limit.set_value(sess.speed_limit_down or 0)
                    ul_enabled.set_value(sess.speed_limit_up_enabled)
                    ul_limit.set_value(sess.speed_limit_up or 0)
                    queue_enabled.set_value(sess.download_queue_enabled)
                    queue_size.set_value(sess.download_queue_size or 5)
                    tr_limits_status.set_text("✔ Valori citite din Transmission")
                    tr_limits_status.classes(replace="text-sm text-green-600")
                except Exception as e:
                    tr_limits_status.set_text(f"✘ {e}")
                    tr_limits_status.classes(replace="text-sm text-red-600")

            def save_tr_limits():
                try:
                    c = _connect()
                    c.set_session(
                        speed_limit_down_enabled=dl_enabled.value,
                        speed_limit_down=int(dl_limit.value or 0),
                        speed_limit_up_enabled=ul_enabled.value,
                        speed_limit_up=int(ul_limit.value or 0),
                        download_queue_enabled=queue_enabled.value,
                        download_queue_size=int(queue_size.value or 5),
                    )
                    ui.notify("✓ Limite salvate în Transmission", type="positive")
                    tr_limits_status.set_text("✔ Aplicate")
                    tr_limits_status.classes(replace="text-sm text-green-600")
                except Exception as e:
                    ui.notify(f"Eroare: {e}", type="negative")

            with ui.row().classes("gap-2 mt-3"):
                ui.button("Salvează", on_click=save_tr_limits).props("color=primary")
                ui.button("Citește din Transmission", on_click=_load_tr_limits).props("outline")

            ui.timer(0.3, _load_tr_limits, once=True)

        # ── Setări globale (shared între toate mașinile) ─────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Global").classes("text-lg font-semibold")
                ui.badge("shared — toate mașinile", color="blue").props("outline")

            ui.label(
                "Aceste setări se aplică pe toate mașinile care folosesc aceeași bază de date."
            ).classes("text-xs text-gray-400")

            # FlareSolverr
            ui.label("FlareSolverr").classes("text-sm font-medium text-gray-500 mt-2")
            with Session() as s:
                fs_url_val = _get_setting(s, "flaresolverr_url", os.getenv("FLARESOLVERR_URL", ""))

            fs_url    = ui.input("URL FlareSolverr", value=fs_url_val,
                                 placeholder="http://localhost:8191").classes("w-full")
            fs_status = ui.label("").classes("text-sm")

            # Jackett
            ui.separator()
            ui.label("Jackett").classes("text-sm font-medium text-gray-500")
            with Session() as s:
                jackett_url_val = _get_setting(s, "jackett_url", os.getenv("JACKETT_URL", "http://localhost:9117"))
                jackett_key_val = _get_setting(s, "jackett_api_key", "")

            jackett_url    = ui.input("URL Jackett", value=jackett_url_val).classes("w-full")
            jackett_key    = ui.input("API Key",     value=jackett_key_val).classes("w-full")
            jackett_status = ui.label("").classes("text-sm")

            def save_global():
                import json
                with Session() as s:
                    _set_setting(s, "flaresolverr_url",      fs_url.value.rstrip("/"))
                    _set_setting(s, "jackett_url",           jackett_url.value.rstrip("/"))
                    _set_setting(s, "jackett_api_key",       jackett_key.value.strip())
                    _set_setting(s, "title_cleanup_tokens",  json.dumps(cleanup_tokens))
                    s.commit()
                ui.notify("✓ Salvat global", type="positive")

            def test_fs():
                import httpx
                fs_status.set_text("Se testează...")
                fs_status.classes(replace="text-sm text-gray-500")
                try:
                    r = httpx.get(f"{fs_url.value.rstrip('/')}/health", timeout=5)
                    if r.status_code == 200:
                        fs_status.set_text("✔ FlareSolverr online")
                        fs_status.classes(replace="text-sm text-green-600")
                    else:
                        fs_status.set_text(f"✘ HTTP {r.status_code}")
                        fs_status.classes(replace="text-sm text-red-600")
                except Exception as e:
                    fs_status.set_text(f"✘ {e}")
                    fs_status.classes(replace="text-sm text-red-600")

            def test_jackett():
                import httpx
                jackett_status.set_text("Se testează...")
                jackett_status.classes(replace="text-sm text-gray-500")
                try:
                    r = httpx.get(
                        f"{jackett_url.value.rstrip('/')}/api/v2.0/server/config",
                        params={"apikey": jackett_key.value.strip()}, timeout=5
                    )
                    if r.status_code == 200:
                        v = r.json().get("version", "?")
                        jackett_status.set_text(f"✔ Jackett v{v} — conectat")
                        jackett_status.classes(replace="text-sm text-green-600")
                    else:
                        jackett_status.set_text(f"✘ HTTP {r.status_code}")
                        jackett_status.classes(replace="text-sm text-red-600")
                except Exception as e:
                    jackett_status.set_text(f"✘ {e}")
                    jackett_status.classes(replace="text-sm text-red-600")

            # Tokeni curățare titluri
            ui.separator()
            ui.label("Afișare titluri — tokeni ignorați").classes("text-sm font-medium text-gray-500")
            ui.label(
                "Cuvinte/grupuri eliminate din titlurile torrent la afișare (Downloads, Search, Logs). "
                "Ex: grupuri release (YIFY, FGT), watermarkuri."
            ).classes("text-xs text-gray-400")

            import json as _json
            with Session() as s:
                _tok_row = s.query(Setting).filter_by(key="title_cleanup_tokens").first()
                cleanup_tokens: list[str] = _json.loads(_tok_row.value) if _tok_row and _tok_row.value else []

            tok_row = ui.row().classes("flex-wrap gap-2 min-h-8 items-center mt-1")

            def _render_tok_chips():
                tok_row.clear()
                with tok_row:
                    for tok in cleanup_tokens:
                        ui.chip(
                            tok, removable=True, color="orange",
                            on_value_change=lambda e, t=tok: (
                                cleanup_tokens.remove(t) if t in cleanup_tokens else None,
                                _render_tok_chips(),
                            ),
                        ).props("dense")

            _render_tok_chips()

            with ui.row().classes("items-center gap-1 mt-1"):
                tok_inp = ui.input(placeholder="ex: YIFY, FGT, Visit.us.at…").classes("w-64")

                def _add_tok(_=None):
                    val = tok_inp.value.strip()
                    if val and val not in cleanup_tokens:
                        cleanup_tokens.append(val)
                        _render_tok_chips()
                    tok_inp.set_value("")

                tok_inp.on("keydown.enter", _add_tok)
                ui.button(icon="add", on_click=_add_tok).props("flat dense round")

            with ui.row().classes("gap-2 mt-3"):
                ui.button("Salvează global", on_click=save_global).props("color=primary")
                ui.button("Test FlareSolverr", on_click=test_fs).props("outline")
                ui.button("Test Jackett", on_click=test_jackett).props("outline")

        # ── Conexiuni sistem ─────────────────────────────────────────────
        with ui.card().classes("w-full max-w-xl gap-2"):
            ui.label("Conexiuni sistem").classes("text-lg font-semibold")
            db_status = ui.label("").classes("text-sm")
            tr_status = ui.label("").classes("text-sm")

            def test_db():
                db_status.set_text("Se testează...")
                db_status.classes(replace="text-sm text-gray-500")
                try:
                    import sqlalchemy
                    with Session() as s:
                        s.execute(sqlalchemy.text("SELECT 1"))
                    db_status.set_text("✔ Baza de date — conectată")
                    db_status.classes(replace="text-sm text-green-600")
                except Exception as e:
                    db_status.set_text(f"✘ DB: {e}")
                    db_status.classes(replace="text-sm text-red-600")

            def test_tr():
                tr_status.set_text("Se testează...")
                tr_status.classes(replace="text-sm text-gray-500")
                try:
                    c = _connect()
                    s = c.get_session()
                    tr_status.set_text(f"✔ Transmission v{s.version} — conectat")
                    tr_status.classes(replace="text-sm text-green-600")
                except Exception as e:
                    tr_status.set_text(f"✘ {e}")
                    tr_status.classes(replace="text-sm text-red-600")

            with ui.row().classes("gap-2"):
                ui.button("Test DB",          on_click=test_db).props("outline")
                ui.button("Test Transmission", on_click=test_tr).props("outline")

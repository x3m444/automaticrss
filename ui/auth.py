from nicegui import ui, app
from core.config import _load_secrets


def _cfg():
    s = _load_secrets()
    return (
        s.get("AUTH_ENABLED", False),
        s.get("AUTH_USERNAME", "admin"),
        s.get("AUTH_PASSWORD", ""),
    )


def check_auth() -> bool:
    enabled, _, _ = _cfg()
    if not enabled:
        return True
    if app.storage.user.get("authenticated"):
        return True
    ui.navigate.to("/login")
    return False


@ui.page("/login")
def login_page():
    enabled, _, _ = _cfg()
    if not enabled or app.storage.user.get("authenticated"):
        ui.navigate.to("/")
        return

    with ui.card().classes("absolute-center w-80 gap-4"):
        ui.label("AutomaticRSS").classes("text-2xl font-bold text-center w-full")

        username = ui.input("Utilizator").classes("w-full")
        password = ui.input("Parolă", password=True, password_toggle_button=True).classes("w-full")
        status   = ui.label("").classes("text-sm text-red-500")

        def try_login():
            _, cfg_user, cfg_pass = _cfg()
            if username.value == cfg_user and password.value == cfg_pass:
                app.storage.user["authenticated"] = True
                ui.navigate.to("/")
            else:
                status.set_text("Utilizator sau parolă incorectă.")

        password.on("keydown.enter", try_login)
        ui.button("Autentificare", on_click=try_login).classes("w-full").props("color=primary")


@ui.page("/logout")
def logout_page():
    app.storage.user["authenticated"] = False
    ui.navigate.to("/login")

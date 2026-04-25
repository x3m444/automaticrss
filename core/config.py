import os
import uuid
import toml
from pathlib import Path

_SECRETS_PATH = Path(__file__).parent.parent / ".secrets" / "secrets.toml"


def _load_secrets() -> dict:
    if _SECRETS_PATH.exists():
        return toml.load(_SECRETS_PATH)
    return {}


def _save_secrets(data: dict):
    _SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SECRETS_PATH, "w") as f:
        toml.dump(data, f)


def _build_db_url() -> str:
    if os.getenv("DB_USER"):
        return (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
            f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
            f"/{os.getenv('DB_NAME')}"
        )
    s = _load_secrets()
    if s:
        return (
            f"postgresql://{s['DB_USER']}:{s['DB_PASS']}"
            f"@{s['DB_HOST']}:{s['DB_PORT']}/{s['DB_NAME']}"
        )
    raise RuntimeError(
        "Credențiale DB lipsă. Setează variabilele de mediu sau creează .secrets/secrets.toml"
    )


def _get_or_create_instance_id() -> str:
    if os.getenv("INSTANCE_ID"):
        return os.getenv("INSTANCE_ID")
    s = _load_secrets()
    if "INSTANCE_ID" in s:
        return s["INSTANCE_ID"]
    instance_id = str(uuid.uuid4())
    s["INSTANCE_ID"] = instance_id
    _save_secrets(s)
    return instance_id


DB_URL       = _build_db_url()
INSTANCE_ID  = _get_or_create_instance_id()
INSTANCE_NAME = os.getenv("INSTANCE_NAME", os.environ.get("COMPUTERNAME", "Default"))

import os
import toml
from pathlib import Path


def _build_db_url() -> str:
    # Prioritate: variabile de mediu (Docker) → .secrets/secrets.toml (dev local)
    if os.getenv("DB_USER"):
        return (
            f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
            f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}"
            f"/{os.getenv('DB_NAME')}"
        )
    secrets_path = Path(__file__).parent.parent / ".secrets" / "secrets.toml"
    if secrets_path.exists():
        s = toml.load(secrets_path)
        return (
            f"postgresql://{s['DB_USER']}:{s['DB_PASS']}"
            f"@{s['DB_HOST']}:{s['DB_PORT']}/{s['DB_NAME']}"
        )
    raise RuntimeError(
        "Credențiale DB lipsă. Setează variabilele de mediu DB_USER/DB_PASS/... "
        "sau creează .secrets/secrets.toml"
    )


DB_URL = _build_db_url()

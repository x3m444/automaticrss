import toml
from pathlib import Path

_secrets_path = Path(__file__).parent.parent / ".secrets" / "secrets.toml"
_secrets = toml.load(_secrets_path)

DB_URL = (
    f"postgresql://{_secrets['DB_USER']}:{_secrets['DB_PASS']}"
    f"@{_secrets['DB_HOST']}:{_secrets['DB_PORT']}/{_secrets['DB_NAME']}"
)

from transmission_rpc import Client
from core.db import Session, Setting


def _get_client() -> Client:
    with Session() as s:
        def get(key, default):
            row = s.query(Setting).filter_by(key=key).first()
            return row.value if row else default

        return Client(
            host=get("transmission_host", "localhost"),
            port=int(get("transmission_port", "9091")),
            username=get("transmission_user", ""),
            password=get("transmission_pass", ""),
        )


def add_magnet(magnet: str) -> str:
    client = _get_client()
    torrent = client.add_torrent(magnet)
    return torrent.hashString


def get_torrents() -> list[dict]:
    client = _get_client()
    return [
        {"hash": t.hashString, "name": t.name, "status": t.status, "progress": t.progress}
        for t in client.get_torrents()
    ]

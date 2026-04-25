"""
Per-instance helpers: ensure the Instance record exists in DB,
read Transmission settings for the current machine.
"""
import os
from datetime import datetime
from core.config import INSTANCE_ID, INSTANCE_NAME
from core.db import Session, Instance, Setting


def get_instance() -> dict:
    """Return current instance settings as a plain dict."""
    with Session() as s:
        inst = s.query(Instance).filter_by(id=INSTANCE_ID).first()
        if inst:
            return {
                "id":                   inst.id,
                "name":                 inst.name,
                "transmission_host":    inst.transmission_host or "localhost",
                "transmission_port":    inst.transmission_port or 9091,
                "transmission_user":    inst.transmission_user or "",
                "transmission_pass":    inst.transmission_pass or "",
                "download_dir":         inst.download_dir or "",
                "disk_cleanup_enabled": inst.disk_cleanup_enabled or False,
                "disk_min_free_gb":     inst.disk_min_free_gb or 10,
                "disk_target_free_gb":  inst.disk_target_free_gb or 20,
            }
    return {
        "id": INSTANCE_ID, "name": INSTANCE_NAME,
        "transmission_host": "localhost", "transmission_port": 9091,
        "transmission_user": "", "transmission_pass": "", "download_dir": "",
        "disk_cleanup_enabled": False, "disk_min_free_gb": 10, "disk_target_free_gb": 20,
    }


def ensure_instance():
    """
    Create the Instance row on first run, migrating existing arss_settings values.
    Updates last_seen_at on every call.
    """
    with Session() as s:
        inst = s.query(Instance).filter_by(id=INSTANCE_ID).first()
        if inst:
            inst.last_seen_at = datetime.utcnow()
            s.commit()
            return

        def _get(key, default=""):
            row = s.query(Setting).filter_by(key=key).first()
            return row.value if row else default

        port_str = _get("transmission_port", "9091")
        try:
            port = int(port_str)
        except ValueError:
            port = 9091

        inst = Instance(
            id=INSTANCE_ID,
            name=INSTANCE_NAME,
            transmission_host=_get("transmission_host", "localhost"),
            transmission_port=port,
            transmission_user=_get("transmission_user", ""),
            transmission_pass=_get("transmission_pass", ""),
            download_dir=_get("transmission_download_dir", ""),
            last_seen_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        s.add(inst)
        s.commit()

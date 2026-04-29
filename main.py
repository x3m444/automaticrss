import logging
import threading
from logging.handlers import RotatingFileHandler


def _setup_logging():
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Fișier — rotire la 5 MB, păstrăm 3 copii
    fh = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Consolă — doar WARNING+ ca să nu fie prea zgomotos
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(ch)

    # Reducem zgomotul din librăriile externe
    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error",
                  "fastapi", "httpx", "httpcore", "watchfiles",
                  "apscheduler.executors", "nicegui"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main():
    _setup_logging()
    from core.db import init_db
    from core.scheduler import start_scheduler
    from ui.main import start_ui

    init_db()
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    start_ui()


if __name__ == "__main__":
    main()

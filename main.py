import threading
from core.db import init_db
from core.indexer_sync import load_cache_from_disk
from core.scheduler import start_scheduler
from ui.main import start_ui


def main():
    init_db()
    load_cache_from_disk()  # încarcă 552 indexeri în RAM o singură dată
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    start_ui()


if __name__ == "__main__":
    main()

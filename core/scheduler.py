import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)
scheduler = BlockingScheduler()

_TASK_GAP_SECONDS = 120   # pauză minimă între două task-uri consecutive
_last_task_end: datetime | None = None



def _rotate_logs():
    """Șterge loguri mai vechi de 7 zile."""
    from core.db import Session, WatchlistLog
    cutoff = datetime.utcnow() - timedelta(days=7)
    with Session() as s:
        deleted = s.query(WatchlistLog).filter(WatchlistLog.ran_at < cutoff).delete()
        s.commit()
    if deleted:
        log.info("[log-rotate] %s rânduri șterse", deleted)


def _poll_watchlist_entries():
    """Verifică fiecare entry watchlist activ și rulează cel mai vechi scadent.
    Impune o pauză de _TASK_GAP_SECONDS între task-uri consecutive."""
    global _last_task_end

    from core.db import Session, Watchlist
    from core.rules_engine import run_watchlist_entry_now
    from core.instance import ensure_instance

    ensure_instance()  # update last_seen_at

    # Respectă pauza minimă între task-uri
    if _last_task_end and (datetime.utcnow() - _last_task_end).total_seconds() < _TASK_GAP_SECONDS:
        return

    now = datetime.utcnow()
    with Session() as s:
        entries = s.query(Watchlist).filter_by(is_active=True).all()
        due = []
        for e in entries:
            interval = e.check_interval_minutes or 120
            if not e.last_run_at or (now - e.last_run_at) >= timedelta(minutes=interval):
                # sortăm după last_run_at: cele mai vechi primele
                due.append((e.id, e.name, e.last_run_at or datetime.min))

    # Rulează un singur task per tick — cel mai demult nerunat
    if not due:
        return

    due.sort(key=lambda x: x[2])
    eid, ename, _ = due[0]
    try:
        result = run_watchlist_entry_now(eid)
        log.info("[WL:%s] %s", ename, result)
    except Exception as ex:
        log.warning("[WL:%s] eroare: %s", ename, ex)
    finally:
        _last_task_end = datetime.utcnow()


def _check_disk_space():
    """Eliberează spațiu dacă disk_cleanup_enabled și spațiul liber < disk_min_free_gb.
    Șterge cele mai vechi torrente (din Transmission + fișiere) până când
    spațiul liber atinge disk_target_free_gb."""
    import shutil
    from core.db import Session, Instance
    from core.config import INSTANCE_ID

    with Session() as s:
        inst = s.query(Instance).filter_by(id=INSTANCE_ID).first()
        if not inst or not inst.disk_cleanup_enabled:
            return
        dl_dir     = inst.download_dir or ""
        min_free   = (inst.disk_min_free_gb or 10) * 1024 ** 3
        target_free = (inst.disk_target_free_gb or 20) * 1024 ** 3

    if not dl_dir:
        return

    usage = shutil.disk_usage(dl_dir)
    if usage.free >= min_free:
        return

    log.info("[disk] Spațiu liber: %.1f GB < prag %.1f GB — declanșez curățare",
             usage.free / 1024**3, min_free / 1024**3)

    try:
        from transmission_rpc import Client
        from core.instance import get_instance
        inst_cfg = get_instance()
        client = Client(
            host=inst_cfg["transmission_host"],
            port=inst_cfg["transmission_port"],
            username=inst_cfg["transmission_user"],
            password=inst_cfg["transmission_pass"],
        )
        torrents = client.get_torrents()
    except Exception as ex:
        log.warning("[disk] Nu pot conecta la Transmission: %s", ex)
        return

    # Sortează după doneDate (cel mai vechi completat primul); finished/seeding
    def _done_ts(t):
        try:
            dd = t.done_date
            return dd.timestamp() if dd else 0
        except Exception:
            return 0

    candidates = [t for t in torrents if t.status in ("seeding", "stopped", "seed_pending")]
    candidates.sort(key=_done_ts)

    freed = 0
    for t in candidates:
        usage = shutil.disk_usage(dl_dir)
        if usage.free >= target_free:
            break
        size = (t.total_size or 0)
        try:
            client.remove_torrent(t.id, delete_data=True)
            freed += size
            log.info("[disk] Șters torrent '%s' (%.1f GB)", t.name, size / 1024**3)
        except Exception as ex:
            log.warning("[disk] Eroare la ștergere '%s': %s", t.name, ex)

    log.info("[disk] Curățare finalizată — eliberat ~%.1f GB", freed / 1024**3)


def start_scheduler():
    scheduler.add_job(
        _poll_watchlist_entries,
        trigger=IntervalTrigger(minutes=1),
        id="poll_watchlist",
        replace_existing=True,
    )
    scheduler.add_job(
        _rotate_logs,
        trigger=IntervalTrigger(hours=24),
        id="rotate_logs",
        replace_existing=True,
    )
    scheduler.add_job(
        _check_disk_space,
        trigger=IntervalTrigger(minutes=30),
        id="disk_cleanup",
        replace_existing=True,
    )
    log.info("Scheduler pornit")
    scheduler.start()

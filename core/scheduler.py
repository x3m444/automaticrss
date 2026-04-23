from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BlockingScheduler()


def start_scheduler():
    from core.indexer_sync import sync_indexers_background

    # sync indexeri o dată pe săptămână
    scheduler.add_job(
        sync_indexers_background,
        trigger=IntervalTrigger(weeks=1),
        id="sync_indexers",
        replace_existing=True,
    )

    scheduler.start()

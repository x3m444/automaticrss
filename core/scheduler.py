import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)
scheduler = BlockingScheduler()


def _poll_feeds():
    """Sondează toate feed-urile RSS active și rulează regulile pe itemele noi."""
    from core.db import Session, Feed
    from core.rss_parser import fetch_feed
    from core.rules_engine import process_item

    with Session() as s:
        feeds = s.query(Feed).filter_by(is_active=True, source_type="rss").all()
        feed_data = [
            {
                "id": f.id,
                "name": f.name,
                "url": f.url,
                "categories": f.categories,
                "poll_interval_minutes": f.poll_interval_minutes or 60,
                "last_checked_at": f.last_checked_at,
            }
            for f in feeds
        ]

    now = datetime.utcnow()
    for feed in feed_data:
        last = feed["last_checked_at"]
        if last and (now - last) < timedelta(minutes=feed["poll_interval_minutes"]):
            continue

        try:
            items = fetch_feed(feed["url"])
            cats = feed.get("categories") or []
            if cats:
                items = [i for i in items if i.get("category") in cats]

            actions = []
            for item in items:
                actions += process_item(item, feed["id"])

            if actions:
                log.info("[%s] %s", feed["name"], " | ".join(actions))

            with Session() as s:
                from core.db import Feed as FeedModel
                row = s.query(FeedModel).filter_by(id=feed["id"]).first()
                if row:
                    row.last_checked_at = now
                    s.commit()

        except Exception as e:
            log.warning("[%s] eroare: %s", feed["name"], e)


def start_scheduler():
    scheduler.add_job(
        _poll_feeds,
        trigger=IntervalTrigger(minutes=5),
        id="poll_feeds",
        replace_existing=True,
    )
    log.info("Scheduler pornit — poll RSS la fiecare 5 minute")
    scheduler.start()

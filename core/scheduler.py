import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)
scheduler = BlockingScheduler()


def _get_flaresolverr_url() -> str | None:
    from core.db import Session, Setting
    with Session() as s:
        row = s.query(Setting).filter_by(key="flaresolverr_url").first()
        return row.value if row and row.value else None


def _poll_feeds():
    from core.db import Session, Feed
    from core.rules_engine import process_item

    with Session() as s:
        feeds = s.query(Feed).filter_by(is_active=True).all()
        feed_data = [
            {
                "id": f.id,
                "name": f.name,
                "url": f.url,
                "source_type": f.source_type or "rss",
                "indexer_id": f.indexer_id,
                "categories": f.categories,
                "poll_interval_minutes": f.poll_interval_minutes or 60,
                "last_checked_at": f.last_checked_at,
            }
            for f in feeds
        ]

    now = datetime.utcnow()
    flaresolverr = _get_flaresolverr_url()

    for feed in feed_data:
        last = feed["last_checked_at"]
        if last and (now - last) < timedelta(minutes=feed["poll_interval_minutes"]):
            continue

        try:
            if feed["source_type"] == "rss":
                _poll_rss(feed)
            elif feed["source_type"] == "scraper":
                _poll_scraper(feed, flaresolverr)

            with Session() as s:
                from core.db import Feed as FeedModel
                row = s.query(FeedModel).filter_by(id=feed["id"]).first()
                if row:
                    row.last_checked_at = now
                    s.commit()

        except Exception as e:
            log.warning("[%s] eroare: %s", feed["name"], e)


def _poll_rss(feed: dict):
    from core.rss_parser import fetch_feed
    from core.rules_engine import process_item

    items = fetch_feed(feed["url"])
    cats = feed.get("categories") or []
    if cats:
        items = [i for i in items if i.get("category") in cats]

    actions = []
    for item in items:
        actions += process_item(item, feed["id"])

    if actions:
        log.info("[%s] %s", feed["name"], " | ".join(actions))


def _poll_scraper(feed: dict, flaresolverr_url: str | None):
    from core.scrapers import get_scraper
    from core.rules_engine import process_item

    scraper = get_scraper(feed["indexer_id"])
    if not scraper:
        log.warning("[%s] scraper necunoscut: %s", feed["name"], feed["indexer_id"])
        return

    cats = feed.get("categories") or []
    items = scraper.fetch_latest(
        categories=cats if cats else None,
        flaresolverr_url=flaresolverr_url,
    )

    actions = []
    for item in items:
        # magnet_getter: called only when a rule matches, avoids fetching detail pages upfront
        item["_magnet_getter"] = lambda url=item["url"]: scraper.get_magnet(
            url, flaresolverr_url=flaresolverr_url
        )
        actions += process_item(item, feed["id"])

    if actions:
        log.info("[%s] %s", feed["name"], " | ".join(actions))


def start_scheduler():
    scheduler.add_job(
        _poll_feeds,
        trigger=IntervalTrigger(minutes=5),
        id="poll_feeds",
        replace_existing=True,
    )
    log.info("Scheduler pornit — poll la fiecare 5 minute")
    scheduler.start()

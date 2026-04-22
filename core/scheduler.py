from apscheduler.schedulers.blocking import BlockingScheduler

scheduler = BlockingScheduler()


def start_scheduler():
    scheduler.start()

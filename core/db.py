from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from core.config import DB_URL

engine = create_engine(DB_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Feed(Base):
    __tablename__ = "arss_feeds"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    source_type = Column(String(50), default="rss")  # rss | scraper
    indexer_id = Column(String(100), nullable=True)   # ex: "mypornclub"
    categories = Column(JSON, nullable=True)
    poll_interval_minutes = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SeenItem(Base):
    __tablename__ = "arss_seen_items"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, nullable=False)
    guid = Column(String(500), nullable=False, unique=True)
    title = Column(Text)
    added_at = Column(DateTime, default=datetime.utcnow)


class Instance(Base):
    __tablename__ = "arss_instances"

    id                = Column(String(36), primary_key=True)   # UUID din secrets.toml
    name              = Column(String(255), nullable=False, default="Default")
    transmission_host = Column(String(255), default="localhost")
    transmission_port = Column(Integer, default=9091)
    transmission_user = Column(String(255), default="")
    transmission_pass = Column(String(255), default="")
    download_dir           = Column(String(500), nullable=True)
    disk_cleanup_enabled   = Column(Boolean, default=False)
    disk_min_free_gb       = Column(Integer, default=10)
    disk_target_free_gb    = Column(Integer, default=20)
    last_seen_at           = Column(DateTime, nullable=True)
    created_at             = Column(DateTime, default=datetime.utcnow)


class Download(Base):
    __tablename__ = "arss_downloads"

    id            = Column(Integer, primary_key=True)
    instance_id   = Column(String(36), nullable=True)   # nullable: backwards compat
    torrent_hash  = Column(String(100), unique=True)
    title         = Column(Text)
    status        = Column(String(50), default="queued")
    size_bytes    = Column(Integer, nullable=True)
    added_at      = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "arss_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)


class Rule(Base):
    __tablename__ = "arss_rules"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    feed_ids = Column(JSON, default=list)      # [] = all active feeds
    # Title matching: AND logic within each list
    must_contain = Column(JSON, nullable=True)      # title must contain ALL terms
    must_not_contain = Column(JSON, nullable=True)  # title must contain NONE of these
    # Per-rule filter overrides (None = inherit global)
    size_min_mb = Column(Integer, nullable=True)
    size_max_gb = Column(Integer, nullable=True)
    seeders_min = Column(Integer, nullable=True)
    quality_banned = Column(JSON, nullable=True)
    resolution_min = Column(String(20), nullable=True)
    languages = Column(JSON, nullable=True)
    title_blacklist = Column(JSON, nullable=True)
    # Destination: stored as slash-joined path segments
    download_subdir = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Watchlist(Base):
    __tablename__ = "arss_watchlist"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    terms = Column(JSON, default=list)        # OR logic — any term in title triggers
    exclusions = Column(JSON, default=list)   # none of these may appear in title
    download_subdir = Column(String(500), nullable=True)
    feed_ids = Column(JSON, default=list)     # [] = toate feed-urile active
    is_active = Column(Boolean, default=True)
    check_interval_minutes = Column(Integer, default=120)
    last_run_at = Column(DateTime, nullable=True)
    log_level = Column(String(20), default="full")  # full | sent | summary
    created_at = Column(DateTime, default=datetime.utcnow)


class WatchlistLog(Base):
    __tablename__ = "arss_wl_logs"

    id = Column(Integer, primary_key=True)
    watchlist_id = Column(Integer, nullable=True)   # nullable: log survives watchlist deletion
    watchlist_name = Column(String(255), nullable=False)
    ran_at = Column(DateTime, default=datetime.utcnow)
    items_checked = Column(Integer, default=0)
    items_sent = Column(Integer, default=0)
    items_blocked = Column(Integer, default=0)
    # entries: [{title, action: "sent"|"blocked"|"excluded", reason: str|None}]
    # empty list when log_detail=False
    entries = Column(JSON, default=list)


def init_db():
    Base.metadata.create_all(engine)

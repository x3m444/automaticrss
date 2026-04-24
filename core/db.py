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


class Download(Base):
    __tablename__ = "arss_downloads"

    id = Column(Integer, primary_key=True)
    torrent_hash = Column(String(100), unique=True)
    title = Column(Text)
    status = Column(String(50), default="queued")
    size_bytes = Column(Integer, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)

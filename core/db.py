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
    source_type = Column(String(50), default="rss")  # rss | cardigann
    indexer_id = Column(String(100), nullable=True)  # pentru cardigann
    poll_interval_minutes = Column(Integer, default=60)
    is_active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FilterRule(Base):
    __tablename__ = "arss_filter_rules"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, nullable=False)
    field = Column(String(50))   # title | size | category
    operator = Column(String(20))  # contains | regex | gt | lt
    value = Column(String(500))
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


def init_db():
    Base.metadata.create_all(engine)

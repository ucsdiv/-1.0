import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON

from app.database import Base


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False, index=True)
    content = Column(Text, default="")
    disk_type = Column(String(32), default="others", index=True)
    url = Column(String(1024), nullable=False)
    password = Column(String(32), default="")
    category_id = Column(Integer, default=0, index=True)
    tags = Column(JSON, default=list)
    images = Column(JSON, default=list)
    source = Column(String(128), default="local")
    is_valid = Column(Boolean, default=True)
    checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, unique=True)
    icon = Column(String(128), default="")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class HotKeyword(Base):
    __tablename__ = "hot_keywords"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(128), nullable=False, unique=True)
    count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)
    keyword = Column(String(256), nullable=False, index=True)
    ip = Column(String(64), default="")
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

from sqlalchemy import Column, Integer, String, Text, DateTime, TIMESTAMP, func
from sqlalchemy.orm import relationship
from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    url = Column(String(255), nullable=False)
    is_show = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class ConfigItem(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    value = Column(Text, nullable=False)


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False)
    search_count = Column(Integer, default=1)
    is_audit = Column(Integer, default=0)
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(2555))
    content = Column(Text)
    url = Column(String(255))
    code = Column(String(50))
    size = Column(String(40))
    category_id = Column(Integer, default=0)
    label = Column(String(40))
    created_at = Column(TIMESTAMP)
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


class Report(Base):
    __tablename__ = "report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(Integer, nullable=False)
    reason = Column(String(255), nullable=False)
    details = Column(Text, nullable=False)
    contact = Column(String(255))
    created_at = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = Column(TIMESTAMP, server_default=func.current_timestamp())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(155), nullable=False)
    created_at = Column(Integer)

"""SQLAlchemy engine, session, and Base."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def init_engine(url: str | None = None):
    global _engine, _SessionLocal
    if url is None:
        url = get_settings().database_url

    _engine = create_engine(
        url,
        connect_args=_connect_args(url),
        future=True,
        pool_pre_ping=True,
    )

    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _sqlite_pragma(dbapi_connection, _):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    _SessionLocal = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return _engine


def get_engine():
    if _engine is None:
        init_engine()
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    if _SessionLocal is None:
        init_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    SessionLocal = get_sessionmaker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """Create all tables via SQLAlchemy metadata — used by tests and dev bootstrap."""
    from app import models_db  # noqa: F401 — register mappers

    Base.metadata.create_all(bind=get_engine())


def drop_all() -> None:
    from app import models_db  # noqa: F401

    Base.metadata.drop_all(bind=get_engine())

"""SQLAlchemy engine/session wiring. Sync session used deliberately for
Module 1's simplicity — parsing is CPU-bound, not I/O-bound, so async
buys nothing here and adds complexity. Later modules that call external
APIs (OpenSSF Scorecard, OSV) will use async httpx clients independently
of this session, so this choice doesn't box us in."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

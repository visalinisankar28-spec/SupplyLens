"""
Shared SQLAlchemy engine/session setup, used by every module
(SBOM Parser, Dependency Graph, Risk Analysis, etc).

If Module 1/2 already defined this file in your repo, keep theirs —
this is provided so Module 3 is importable/runnable standalone.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

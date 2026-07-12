"""Shared fixtures for the test suite."""
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 7, 12, tzinfo=timezone.utc)


@pytest.fixture
def days_ago():
    """Factory fixture: days_ago(30) -> a datetime 30 days before `now`."""
    base = datetime(2026, 7, 12, tzinfo=timezone.utc)

    def _make(days: int) -> datetime:
        return base - timedelta(days=days)

    return _make

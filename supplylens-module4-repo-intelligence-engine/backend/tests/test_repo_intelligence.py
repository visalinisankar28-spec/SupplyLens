"""
Tests for Module 4 — Repository & Maintenance Intelligence Engine.

Run with: pytest backend/tests/test_repo_intelligence.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.modules.repo_intelligence.repo_metadata_client import parse_repo_url
from app.modules.repo_intelligence.service import (
    _activity_score,
    _bus_factor_score,
    _maintenance_score,
    _top_contributor_share,
)


# --------------------------------------------------------------------- #
# parse_repo_url
# --------------------------------------------------------------------- #

def test_parse_repo_url_github():
    host, owner, repo = parse_repo_url("https://github.com/expressjs/express")
    assert host == "github.com"
    assert owner == "expressjs"
    assert repo == "express"


def test_parse_repo_url_strips_git_suffix():
    _, owner, repo = parse_repo_url("https://github.com/expressjs/express.git")
    assert owner == "expressjs"
    assert repo == "express"


def test_parse_repo_url_rejects_non_github():
    with pytest.raises(ValueError):
        parse_repo_url("https://gitlab.com/foo/bar")


# --------------------------------------------------------------------- #
# Maintenance score banding
# --------------------------------------------------------------------- #

def _days_ago(n: int) -> datetime:
    return datetime.utcnow() - timedelta(days=n)


@pytest.mark.parametrize(
    "days,expected_score",
    [
        (10, 0.0),
        (90, 0.0),
        (91, 2.5),
        (180, 2.5),
        (181, 5.0),
        (365, 5.0),
        (366, 7.5),
        (730, 7.5),
        (731, 10.0),
    ],
)
def test_maintenance_score_bands(days, expected_score):
    score, _ = _maintenance_score(last_release_at=_days_ago(days), last_commit_at=None)
    assert score == expected_score


def test_maintenance_score_no_history_is_worst_case():
    score, reason = _maintenance_score(None, None)
    assert score == 10.0
    assert "unmaintained" in reason.lower()


def test_maintenance_score_uses_most_recent_of_release_or_commit():
    # commit is recent even though release is old -> should count as active
    score, _ = _maintenance_score(last_release_at=_days_ago(800), last_commit_at=_days_ago(5))
    assert score == 0.0


# --------------------------------------------------------------------- #
# Activity score
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "release_count,expected_score",
    [
        (0, 10.0),
        (1, 8.5),
        (7, 0.0),   # capped
        (20, 0.0),  # still capped
    ],
)
def test_activity_score(release_count, expected_score):
    score, _ = _activity_score(release_count)
    assert score == expected_score


# --------------------------------------------------------------------- #
# Bus factor / contributor concentration
# --------------------------------------------------------------------- #

def test_top_contributor_share_computation():
    contributors = [
        {"login": "alice", "contributions": 900},
        {"login": "bob", "contributions": 100},
    ]
    assert _top_contributor_share(contributors) == 90.0


def test_top_contributor_share_empty_list():
    assert _top_contributor_share([]) is None


@pytest.mark.parametrize(
    "share,expected_score",
    [
        (None, 5.0),
        (10, 0.0),
        (29.9, 0.0),
        (30, 3.0),
        (49.9, 3.0),
        (50, 6.0),
        (74.9, 6.0),
        (75, 10.0),
        (100, 10.0),
    ],
)
def test_bus_factor_score_bands(share, expected_score):
    score, _ = _bus_factor_score(share)
    assert score == expected_score

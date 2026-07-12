"""
Unit tests for the pure/deterministic pieces of the governance service:
bucketing and normalization. DB-backed functions are covered by
test_router.py with a mocked session / test database fixture.
"""

import pytest

from app.modules.governance.schemas import RiskBucket
from app.modules.governance.service import _bucket_for, _normalize


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, RiskBucket.LOW),
        (39.9, RiskBucket.LOW),
        (40, RiskBucket.MEDIUM),
        (69.9, RiskBucket.MEDIUM),
        (70, RiskBucket.HIGH),
        (89.9, RiskBucket.HIGH),
        (90, RiskBucket.CRITICAL),
        (100, RiskBucket.CRITICAL),
    ],
)
def test_bucket_for_thresholds(score, expected):
    assert _bucket_for(score) == expected


def test_normalize_scales_to_zero_one():
    values = [10, 20, 30, 40]
    normalized = _normalize(values)
    assert normalized[0] == 0.0
    assert normalized[-1] == 1.0
    assert all(0.0 <= v <= 1.0 for v in normalized)


def test_normalize_handles_degenerate_range():
    # All identical values -> no divide-by-zero, everything maps to 0.0
    values = [5, 5, 5]
    assert _normalize(values) == [0.0, 0.0, 0.0]


def test_normalize_handles_empty_list():
    assert _normalize([]) == []


def test_remediation_priority_weights_sum_to_one():
    # Documented in README_MODULE6.md section 5.1 — guard against drift.
    weights = {"risk": 0.35, "blast_radius": 0.30, "cvss": 0.20, "patch_penalty": 0.15}
    assert round(sum(weights.values()), 5) == 1.0

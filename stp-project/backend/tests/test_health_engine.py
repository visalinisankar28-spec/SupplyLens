"""
Unit tests for the Dependency Health Index algorithm.

These tests deliberately cover the decision boundaries described in the
documentation (Healthy / Stable / Needs Attention / High Maintenance Risk)
so that a reviewer can verify the algorithm's behavior matches its spec
without needing to trust the implementation blindly.
"""
from app.models.health_profile import HealthCategory
from app.services.health_engine import HealthInputs, compute_dependency_health


def test_actively_maintained_component_is_healthy(now, days_ago):
    """A well-maintained, well-supported, recently-released package should be Healthy."""
    inputs = HealthInputs(
        scorecard_overall_score=8.5,
        scorecard_maintained_check=9.0,
        contributors_count=25,
        is_archived=False,
        last_release_at=days_ago(30),
        last_commit_at=days_ago(5),
        now=now,
    )
    result = compute_dependency_health(inputs)
    assert result.dhi_category == HealthCategory.HEALTHY
    assert result.dhi_score >= 80


def test_archived_repo_is_always_high_risk_regardless_of_history(now, days_ago):
    """
    An archived repository must be classified High Maintenance Risk even if
    its historical activity metrics look good - abandonment is a hard
    override, not just another weighted factor.
    """
    inputs = HealthInputs(
        scorecard_overall_score=9.0,
        scorecard_maintained_check=9.0,
        contributors_count=20,
        is_archived=True,
        last_release_at=days_ago(10),
        last_commit_at=days_ago(5),
        now=now,
    )
    result = compute_dependency_health(inputs)
    assert result.dhi_category == HealthCategory.HIGH_MAINTENANCE_RISK
    assert result.dhi_score <= 10
    assert any("archived" in note.lower() for note in result.explanation)


def test_single_maintainer_project_is_flagged_but_not_automatically_unhealthy(now, days_ago):
    """
    A single-maintainer project with otherwise good activity should be
    penalized on community resilience but not necessarily fall below
    'Stable' - per the documentation, single-maintainer is a flag for
    review, not an automatic security verdict.
    """
    inputs = HealthInputs(
        scorecard_overall_score=7.0,
        scorecard_maintained_check=8.0,
        contributors_count=1,
        is_archived=False,
        last_release_at=days_ago(60),
        last_commit_at=days_ago(10),
        now=now,
    )
    result = compute_dependency_health(inputs)
    assert result.community_resilience_score == 20.0
    assert any("bus-factor" in note.lower() for note in result.explanation)
    assert result.dhi_category in (HealthCategory.STABLE, HealthCategory.NEEDS_ATTENTION)


def test_stale_component_with_no_recent_release_needs_attention_or_worse(now, days_ago):
    inputs = HealthInputs(
        scorecard_overall_score=4.0,
        scorecard_maintained_check=3.0,
        contributors_count=3,
        is_archived=False,
        last_release_at=days_ago(800),
        last_commit_at=days_ago(400),
        now=now,
    )
    result = compute_dependency_health(inputs)
    assert result.release_cadence_score == 15.0
    assert result.dhi_category in (
        HealthCategory.NEEDS_ATTENTION,
        HealthCategory.HIGH_MAINTENANCE_RISK,
    )


def test_completely_unknown_component_degrades_conservatively_not_optimistically(now):
    """
    Missing data across the board must not default to a neutral/high score -
    an unscored, unresolved component is treated as higher risk, matching
    the "we don't silently trust what we can't verify" principle.
    """
    inputs = HealthInputs(
        scorecard_overall_score=None,
        scorecard_maintained_check=None,
        contributors_count=None,
        is_archived=False,
        last_release_at=None,
        last_commit_at=None,
        now=now,
    )
    result = compute_dependency_health(inputs)
    assert result.dhi_score < 40
    assert result.dhi_category == HealthCategory.HIGH_MAINTENANCE_RISK

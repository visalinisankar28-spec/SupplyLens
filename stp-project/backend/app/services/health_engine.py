"""
Dependency Health Engine.

Computes the Dependency Health Index (DHI) for a single component from raw
signals already collected by the Scorecard and Registry clients.

Design principles (deliberate, matching the project documentation):
  - Fully deterministic and explainable. No machine learning. Every score
    can be traced back to a named, documented threshold.
  - An archived repository is a hard override: an abandoned project cannot
    be rated "Healthy" no matter how good its historical metrics were.
  - Missing data degrades gracefully to a conservative (low) sub-score
    rather than being silently excluded from the weighted average - a
    component we know nothing about should not look artificially healthy.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.health_profile import HealthCategory

settings = get_settings()


@dataclass
class HealthInputs:
    """All raw signals the DHI algorithm needs for one component."""

    scorecard_overall_score: float | None  # 0-10 scale from OpenSSF Scorecard
    scorecard_maintained_check: float | None  # 0-10 scale
    contributors_count: int | None
    is_archived: bool
    last_release_at: datetime | None
    last_commit_at: datetime | None
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class HealthResult:
    """Output of the DHI computation, ready to persist."""

    maintenance_activity_score: float
    release_cadence_score: float
    community_resilience_score: float
    security_hygiene_score: float
    dhi_score: float
    dhi_category: HealthCategory
    explanation: list[str]
    days_since_last_release: int | None
    days_since_last_commit: int | None


def _days_since(reference: datetime | None, now: datetime) -> int | None:
    if reference is None:
        return None
    return (now - reference).days


def _score_maintenance_activity(inputs: HealthInputs, days_since_commit: int | None) -> tuple[float, str | None]:
    """
    Primary signal: OpenSSF Scorecard's 'Maintained' check, which itself
    tracks commit/issue activity over a rolling 90-day window. Falls back
    to our own commit-recency thresholds only when Scorecard has no data
    for this repository (e.g. it isn't hosted on GitHub, or hasn't been
    scored yet).
    """
    if inputs.scorecard_maintained_check is not None:
        score = inputs.scorecard_maintained_check * 10  # 0-10 -> 0-100
        note = None if score >= 70 else "Low recent maintenance activity (OpenSSF Scorecard 'Maintained' check)"
        return score, note

    if days_since_commit is None:
        return 10.0, "No commit history available - treated as unknown/high risk"
    if days_since_commit <= 90:
        return 100.0, None
    if days_since_commit <= 180:
        return 70.0, None
    if days_since_commit <= 365:
        return 40.0, "No commits in over 6 months"
    return 10.0, f"No commits in {days_since_commit} days"


def _score_release_cadence(days_since_release: int | None) -> tuple[float, str | None]:
    if days_since_release is None:
        return 0.0, "No release history found in the package registry"
    if days_since_release <= 180:
        return 100.0, None
    if days_since_release <= 365:
        return 75.0, None
    if days_since_release <= 730:
        return 40.0, "No new release in over a year"
    return 15.0, f"No new release in {days_since_release} days (over 2 years)"


def _score_community_resilience(contributors_count: int | None) -> tuple[float, str | None]:
    if contributors_count is None:
        return 10.0, "Contributor count unavailable"
    if contributors_count >= 10:
        return 100.0, None
    if contributors_count >= 5:
        return 75.0, None
    if contributors_count >= 2:
        return 50.0, "Small contributor base (2-4 active contributors)"
    if contributors_count == 1:
        return 20.0, "Single-maintainer project - high bus-factor risk"
    return 10.0, "No contributor data found"


def _score_security_hygiene(overall_scorecard_score: float | None) -> tuple[float, str | None]:
    """
    Secondary, contextual signal: OpenSSF Scorecard's overall score reflects
    engineering practice hygiene (branch protection, code review, pinned
    dependencies, etc.) - this is about *process maturity*, not "does it
    have a CVE", and is intentionally weighted lower than the direct
    maintenance/release signals.
    """
    if overall_scorecard_score is None:
        return 30.0, "No OpenSSF Scorecard data available for this repository"
    score = overall_scorecard_score * 10
    note = None if score >= 50 else "Below-average OpenSSF Scorecard security practice score"
    return score, note


def _categorize(dhi_score: float, is_archived: bool) -> HealthCategory:
    if is_archived:
        return HealthCategory.HIGH_MAINTENANCE_RISK
    if dhi_score >= settings.dhi_threshold_healthy:
        return HealthCategory.HEALTHY
    if dhi_score >= settings.dhi_threshold_stable:
        return HealthCategory.STABLE
    if dhi_score >= settings.dhi_threshold_needs_attention:
        return HealthCategory.NEEDS_ATTENTION
    return HealthCategory.HIGH_MAINTENANCE_RISK


def compute_dependency_health(inputs: HealthInputs) -> HealthResult:
    """
    Compute the Dependency Health Index for one component.

    Complexity: O(1) - a fixed number of threshold comparisons and one
    weighted sum. Called once per component per analysis run.
    """
    days_since_release = _days_since(inputs.last_release_at, inputs.now)
    days_since_commit = _days_since(inputs.last_commit_at, inputs.now)

    mas, mas_note = _score_maintenance_activity(inputs, days_since_commit)
    rcs, rcs_note = _score_release_cadence(days_since_release)
    crs, crs_note = _score_community_resilience(inputs.contributors_count)
    shs, shs_note = _score_security_hygiene(inputs.scorecard_overall_score)

    dhi_score = (
        settings.dhi_weight_maintenance_activity * mas
        + settings.dhi_weight_release_cadence * rcs
        + settings.dhi_weight_community_resilience * crs
        + settings.dhi_weight_security_hygiene * shs
    )

    explanation = [note for note in (mas_note, rcs_note, crs_note, shs_note) if note]
    if inputs.is_archived:
        explanation.insert(0, "Repository is archived - project is no longer maintained")

    category = _categorize(dhi_score, inputs.is_archived)
    # An archived repo is scored at 10 regardless of its historical metrics -
    # the override affects the *category*, and we also cap the numeric score
    # so the dashboard's sort order stays consistent with the category.
    if inputs.is_archived:
        dhi_score = min(dhi_score, 10.0)

    return HealthResult(
        maintenance_activity_score=round(mas, 1),
        release_cadence_score=round(rcs, 1),
        community_resilience_score=round(crs, 1),
        security_hygiene_score=round(shs, 1),
        dhi_score=round(dhi_score, 1),
        dhi_category=category,
        explanation=explanation,
        days_since_last_release=days_since_release,
        days_since_last_commit=days_since_commit,
    )

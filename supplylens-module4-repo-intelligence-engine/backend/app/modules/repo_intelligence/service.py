"""
RepoIntelligenceEngine — core algorithms for Module 4.

Combines OpenSSF Scorecard results with raw GitHub metadata into an
explainable repo_health_score per package. Every weight used below is a
named constant, not a buried magic number, so the composite can be
challenged/tuned during review without touching logic.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.modules.repo_intelligence import models
from app.modules.repo_intelligence.repo_metadata_client import (
    RepoMetadataClient,
    parse_repo_url,
)
from app.modules.repo_intelligence.scorecard_client import ScorecardClient
from app.modules.repo_intelligence.schemas import ScanResult

logger = logging.getLogger(__name__)

# Composite weights for repo_health_score. Must sum to 1.0.
SCORE_WEIGHTS = {
    "scorecard": 0.40,
    "maintenance": 0.25,
    "bus_factor": 0.20,
    "activity": 0.15,
}

BUS_FACTOR_ALERT_THRESHOLD = 7.0  # used by the single-points-of-failure endpoint


@dataclass
class RepoTarget:
    """Minimal contract: which package maps to which upstream repo."""

    package_id: str
    repo_url: str


def _maintenance_score(last_release_at: Optional[datetime], last_commit_at: Optional[datetime]) -> tuple[float, str]:
    candidates = [d for d in (last_release_at, last_commit_at) if d is not None]
    if not candidates:
        return 10.0, "No release or commit history found; treated as unmaintained."

    staleness_days = (datetime.utcnow() - max(candidates)).days

    if staleness_days <= 90:
        return 0.0, f"Active — last activity {staleness_days} day(s) ago."
    if staleness_days <= 180:
        return 2.5, f"Slowing down — last activity {staleness_days} days ago."
    if staleness_days <= 365:
        return 5.0, f"Aging — last activity {staleness_days} days ago."
    if staleness_days <= 730:
        return 7.5, f"Stale — last activity {staleness_days} days ago (6mo-2yr)."
    return 10.0, f"Likely unmaintained — last activity {staleness_days} days ago (2+ years)."


def _activity_score(release_count_last_year: Optional[int]) -> tuple[float, str]:
    count = release_count_last_year or 0
    score = max(0.0, 10.0 - min(10.0, count * 1.5))
    return round(score, 2), f"{count} release(s) in the last 12 months."


def _bus_factor_score(top_contributor_share: Optional[float]) -> tuple[float, str]:
    if top_contributor_share is None:
        return 5.0, "Contributor data unavailable; treated as moderate risk."
    if top_contributor_share < 30:
        return 0.0, f"Well distributed — top contributor holds {top_contributor_share:.0f}% of commits."
    if top_contributor_share < 50:
        return 3.0, f"Moderately concentrated — top contributor holds {top_contributor_share:.0f}% of commits."
    if top_contributor_share < 75:
        return 6.0, f"Concentrated — top contributor holds {top_contributor_share:.0f}% of commits."
    return 10.0, f"Single point of failure — top contributor holds {top_contributor_share:.0f}% of commits."


def _top_contributor_share(contributors: list[dict[str, Any]]) -> Optional[float]:
    if not contributors:
        return None
    total = sum(c.get("contributions", 0) for c in contributors)
    if total == 0:
        return None
    top = max(c.get("contributions", 0) for c in contributors)
    return round((top / total) * 100, 2)


class RepoIntelligenceEngine:
    def __init__(
        self,
        db: Session,
        scorecard_client: Optional[ScorecardClient] = None,
        metadata_client: Optional[RepoMetadataClient] = None,
    ) -> None:
        self.db = db
        self.scorecard_client = scorecard_client or ScorecardClient()
        self.metadata_client = metadata_client or RepoMetadataClient()

    async def scan_application(
        self, application_id: str, targets: list[RepoTarget]
    ) -> ScanResult:
        start = time.perf_counter()
        profiles_generated = 0

        for target in targets:
            try:
                profile = await self._build_profile(target)
            except ValueError as exc:
                logger.warning("Skipping unparseable repo URL %s: %s", target.repo_url, exc)
                continue

            # Upsert-by-package_id semantics
            existing = (
                self.db.query(models.RepositoryProfile)
                .filter_by(package_id=target.package_id)
                .one_or_none()
            )
            if existing:
                for key, value in profile.items():
                    setattr(existing, key, value)
            else:
                self.db.add(models.RepositoryProfile(**profile))
            profiles_generated += 1

        self.db.commit()
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ScanResult(
            application_id=application_id,
            repositories_scanned=len(targets),
            profiles_generated=profiles_generated,
            duration_ms=duration_ms,
        )

    async def _build_profile(self, target: RepoTarget) -> dict[str, Any]:
        host, owner, repo = parse_repo_url(target.repo_url)

        summary = await self.metadata_client.get_repo_summary(owner, repo)
        last_release_at = await self.metadata_client.get_latest_release(owner, repo)
        release_count = await self.metadata_client.get_release_count_last_year(owner, repo)
        contributors = await self.metadata_client.get_contributor_commit_shares(owner, repo)
        top_share = _top_contributor_share(contributors)

        scorecard_payload = await self.scorecard_client.get_scorecard(host, f"{owner}/{repo}")
        scorecard_score = (
            ScorecardClient.extract_overall_score(scorecard_payload) if scorecard_payload else None
        )
        scorecard_checks = (
            ScorecardClient.extract_checks(scorecard_payload) if scorecard_payload else None
        )

        last_commit_at = _parse_pushed_at(summary.get("pushed_at"))

        maint_score, maint_reason = _maintenance_score(last_release_at, last_commit_at)
        act_score, act_reason = _activity_score(release_count)
        bus_score, bus_reason = _bus_factor_score(top_share)

        # If Scorecard has no cached result for this repo, fall back to
        # a neutral midpoint rather than crashing or silently zeroing risk.
        scorecard_for_composite = scorecard_score if scorecard_score is not None else 5.0

        repo_health = round(
            SCORE_WEIGHTS["scorecard"] * (10 - scorecard_for_composite)
            + SCORE_WEIGHTS["maintenance"] * maint_score
            + SCORE_WEIGHTS["bus_factor"] * bus_score
            + SCORE_WEIGHTS["activity"] * act_score,
            2,
        )

        explanation = {
            "scorecard_reasoning": (
                f"OpenSSF Scorecard aggregate: {scorecard_score:.1f}/10."
                if scorecard_score is not None
                else "No OpenSSF Scorecard result cached for this repo; used neutral default (5.0)."
            ),
            "maintenance_reasoning": maint_reason,
            "activity_reasoning": act_reason,
            "bus_factor_reasoning": bus_reason,
            "weights": SCORE_WEIGHTS,
        }

        return dict(
            package_id=target.package_id,
            repo_url=target.repo_url,
            repo_platform="github",
            stars=summary.get("stars"),
            forks=summary.get("forks"),
            open_issues=summary.get("open_issues"),
            contributors_count=len(contributors) or None,
            last_commit_at=last_commit_at,
            last_release_at=last_release_at,
            release_count_last_year=release_count,
            top_contributor_commit_share=top_share,
            scorecard_overall_score=scorecard_score,
            scorecard_checks=scorecard_checks,
            maintenance_score=maint_score,
            activity_score=act_score,
            bus_factor_score=bus_score,
            repo_health_score=repo_health,
            explanation=explanation,
            fetched_at=datetime.utcnow(),
        )


def _parse_pushed_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.strptime(value.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)

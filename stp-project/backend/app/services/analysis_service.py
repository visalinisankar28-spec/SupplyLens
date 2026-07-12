"""
Analysis orchestration service.

Coordinates the full pipeline for one component:
  registry lookup -> repo resolution -> Scorecard lookup -> DHI computation
  -> persistence

Kept separate from the API layer so it can be reused by a future CI/CD
webhook or a background worker without going through HTTP.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.component import Component
from app.models.health_profile import DependencyHealthProfile
from app.services.health_engine import HealthInputs, compute_dependency_health
from app.services.registry_client import RegistryClient
from app.services.repo_resolver import resolve_github_repo
from app.services.scorecard_client import ScorecardClient

logger = logging.getLogger(__name__)


class DependencyHealthAnalysisService:
    """Runs the health-analysis pipeline for one or many components."""

    def __init__(
        self,
        db: Session,
        registry_client: RegistryClient | None = None,
        scorecard_client: ScorecardClient | None = None,
    ) -> None:
        self._db = db
        self._registry_client = registry_client or RegistryClient()
        self._scorecard_client = scorecard_client or ScorecardClient()

    def analyze_component(self, component: Component, force_refresh: bool = False) -> DependencyHealthProfile:
        """Analyze a single component and upsert its health profile."""
        existing = (
            self._db.query(DependencyHealthProfile)
            .filter(DependencyHealthProfile.component_id == component.id)
            .one_or_none()
        )
        if existing is not None and not force_refresh:
            return existing

        registry_metadata = self._registry_client.get_metadata(component.ecosystem, component.name)
        repo_ref = resolve_github_repo(registry_metadata.repository_url if registry_metadata else None)

        scorecard_result = None
        if repo_ref is not None:
            scorecard_result = self._scorecard_client.get_scorecard(repo_ref.owner, repo_ref.repo)

        # NOTE: contributors_count and archival/last-commit status ideally
        # come from the GitHub API directly (Scorecard's public API does not
        # expose these as raw values, only as pre-scored checks). For the
        # MVP we derive a contributor proxy from the Scorecard "Contributors"
        # check score, documented as a known simplification - see README.
        contributors_proxy = (
            _contributors_check_to_count(scorecard_result.contributors_check_score)
            if scorecard_result
            else None
        )

        inputs = HealthInputs(
            scorecard_overall_score=scorecard_result.overall_score if scorecard_result else None,
            scorecard_maintained_check=scorecard_result.maintained_check_score if scorecard_result else None,
            contributors_count=contributors_proxy,
            is_archived=False,  # Future improvement: GitHub API repo.archived field
            last_release_at=registry_metadata.last_release_at if registry_metadata else None,
            last_commit_at=None,  # Future improvement: GitHub API pushed_at field
            now=datetime.now(timezone.utc),
        )
        result = compute_dependency_health(inputs)

        profile = existing or DependencyHealthProfile(component_id=component.id)
        profile.repo_url = registry_metadata.repository_url if registry_metadata else None
        profile.repo_resolved = repo_ref is not None
        profile.scorecard_overall_score = inputs.scorecard_overall_score
        profile.scorecard_maintained_check = inputs.scorecard_maintained_check
        profile.scorecard_raw_checks = scorecard_result.raw_checks if scorecard_result else None
        profile.contributors_count = inputs.contributors_count
        profile.is_archived = inputs.is_archived
        profile.days_since_last_release = result.days_since_last_release
        profile.days_since_last_commit = result.days_since_last_commit
        profile.maintenance_activity_score = result.maintenance_activity_score
        profile.release_cadence_score = result.release_cadence_score
        profile.community_resilience_score = result.community_resilience_score
        profile.security_hygiene_score = result.security_hygiene_score
        profile.dhi_score = result.dhi_score
        profile.dhi_category = result.dhi_category
        profile.explanation = result.explanation

        self._db.add(profile)
        self._db.commit()
        self._db.refresh(profile)
        return profile

    def analyze_sbom(self, sbom_id: uuid.UUID, force_refresh: bool = False) -> list[DependencyHealthProfile]:
        """Analyze every component belonging to a given SBOM."""
        components = self._db.query(Component).filter(Component.sbom_id == sbom_id).all()
        profiles = []
        for component in components:
            try:
                profiles.append(self.analyze_component(component, force_refresh=force_refresh))
            except Exception:  # noqa: BLE001 - one bad component must not fail the batch
                logger.exception("Health analysis failed for component %s (%s)", component.id, component.purl)
        return profiles

    def close(self) -> None:
        self._registry_client.close()
        self._scorecard_client.close()


def _contributors_check_to_count(check_score: float | None) -> int | None:
    """
    Map Scorecard's 0-10 'Contributors' check score to an approximate
    contributor-count bucket for our thresholds. Documented simplification:
    replace with a direct GitHub API contributor count in a future version.
    """
    if check_score is None:
        return None
    if check_score >= 8:
        return 10
    if check_score >= 5:
        return 5
    if check_score >= 2:
        return 2
    return 1

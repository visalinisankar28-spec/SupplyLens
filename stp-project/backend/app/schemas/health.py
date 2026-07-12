"""
Pydantic schemas for the Dependency Health Intelligence API.

These are intentionally separate from the SQLAlchemy models: the API
contract should be free to evolve independently of the storage schema.
"""
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.health_profile import HealthCategory


class HealthProfileResponse(BaseModel):
    """Full health profile for a single component, returned to API clients."""

    model_config = ConfigDict(from_attributes=True)

    component_id: uuid.UUID
    repo_url: str | None
    repo_resolved: bool

    scorecard_overall_score: float | None
    contributors_count: int | None
    is_archived: bool
    days_since_last_release: int | None
    days_since_last_commit: int | None

    maintenance_activity_score: float
    release_cadence_score: float
    community_resilience_score: float
    security_hygiene_score: float

    dhi_score: float = Field(..., ge=0, le=100)
    dhi_category: HealthCategory
    explanation: list[str]


class SbomHealthSummary(BaseModel):
    """Aggregate health summary for every component in one SBOM."""

    sbom_id: uuid.UUID
    total_components: int
    analyzed_components: int
    category_breakdown: dict[str, int]
    average_dhi_score: float
    profiles: list[HealthProfileResponse]


class AnalyzeSbomRequest(BaseModel):
    """Request body to trigger a health analysis run for an SBOM."""

    force_refresh: bool = Field(
        default=False,
        description="If true, re-query external APIs even for components "
        "that already have a recent health profile.",
    )

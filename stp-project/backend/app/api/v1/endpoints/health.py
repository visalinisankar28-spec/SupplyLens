"""
Dependency Health Intelligence endpoints.

Endpoint summary:
  POST /api/v1/health/sbom/{sbom_id}/analyze  - run/refresh analysis for an SBOM
  GET  /api/v1/health/sbom/{sbom_id}           - get the health summary for an SBOM
  GET  /api/v1/health/component/{component_id} - get one component's health profile
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.component import Component
from app.models.health_profile import DependencyHealthProfile
from app.schemas.health import AnalyzeSbomRequest, HealthProfileResponse, SbomHealthSummary
from app.services.analysis_service import DependencyHealthAnalysisService

router = APIRouter(prefix="/health", tags=["Dependency Health"])


@router.post("/sbom/{sbom_id}/analyze", response_model=SbomHealthSummary)
def analyze_sbom(
    sbom_id: uuid.UUID,
    request: AnalyzeSbomRequest,
    db: Session = Depends(get_db),
) -> SbomHealthSummary:
    """Run (or refresh) Dependency Health analysis for every component in an SBOM."""
    total_components = db.query(Component).filter(Component.sbom_id == sbom_id).count()
    if total_components == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No components found for SBOM {sbom_id}")

    service = DependencyHealthAnalysisService(db=db)
    try:
        profiles = service.analyze_sbom(sbom_id, force_refresh=request.force_refresh)
    finally:
        service.close()

    return _build_summary(sbom_id, total_components, profiles)


@router.get("/sbom/{sbom_id}", response_model=SbomHealthSummary)
def get_sbom_health(sbom_id: uuid.UUID, db: Session = Depends(get_db)) -> SbomHealthSummary:
    """Retrieve the already-computed health summary for an SBOM (no external calls)."""
    total_components = db.query(Component).filter(Component.sbom_id == sbom_id).count()
    if total_components == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No components found for SBOM {sbom_id}")

    profiles = (
        db.query(DependencyHealthProfile)
        .join(Component)
        .filter(Component.sbom_id == sbom_id)
        .all()
    )
    return _build_summary(sbom_id, total_components, profiles)


@router.get("/component/{component_id}", response_model=HealthProfileResponse)
def get_component_health(component_id: uuid.UUID, db: Session = Depends(get_db)) -> HealthProfileResponse:
    """Retrieve the health profile for a single component."""
    profile = (
        db.query(DependencyHealthProfile)
        .filter(DependencyHealthProfile.component_id == component_id)
        .one_or_none()
    )
    if profile is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No health profile for component {component_id}. Run analysis first.",
        )
    return HealthProfileResponse.model_validate(profile)


def _build_summary(
    sbom_id: uuid.UUID, total_components: int, profiles: list[DependencyHealthProfile]
) -> SbomHealthSummary:
    """Compute the aggregate breakdown shown at the top of the dashboard."""
    category_breakdown: dict[str, int] = {}
    for profile in profiles:
        key = profile.dhi_category.value
        category_breakdown[key] = category_breakdown.get(key, 0) + 1

    average_score = round(sum(p.dhi_score for p in profiles) / len(profiles), 1) if profiles else 0.0

    return SbomHealthSummary(
        sbom_id=sbom_id,
        total_components=total_components,
        analyzed_components=len(profiles),
        category_breakdown=category_breakdown,
        average_dhi_score=average_score,
        profiles=[HealthProfileResponse.model_validate(p) for p in profiles],
    )

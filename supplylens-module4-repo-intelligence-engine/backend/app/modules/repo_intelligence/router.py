"""
FastAPI routes for Module 4 — Repository & Maintenance Intelligence Engine.
Mounted under /api/v1/repo-intelligence in app/main.py.
"""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.repo_intelligence import models
from app.modules.repo_intelligence.schemas import (
    RepositoryProfileOut,
    ScanRequest,
    ScanResult,
    SinglePointOfFailure,
)
from app.modules.repo_intelligence.service import (
    BUS_FACTOR_ALERT_THRESHOLD,
    RepoIntelligenceEngine,
    RepoTarget,
)

router = APIRouter(prefix="/api/v1/repo-intelligence", tags=["Repository Intelligence"])


def _load_repo_targets(db: Session, application_id: UUID) -> List[RepoTarget]:
    """
    Bridges to Module 1/2's schema: pulls the upstream repo URL for every
    package resolved for this application. Assumes `packages.repo_url` was
    populated during SBOM parsing (common CycloneDX/SPDX field); adjust the
    SQL if your schema stores this differently.
    """
    rows = db.execute(
        text(
            """
            SELECT p.id AS package_id, p.repo_url
            FROM packages p
            JOIN application_packages ap ON ap.package_id = p.id
            WHERE ap.application_id = :app_id AND p.repo_url IS NOT NULL
            """
        ),
        {"app_id": str(application_id)},
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                "No packages with a known repository URL found for this application. "
                "Ensure Module 1's SBOM Parser captured repo_url during parsing."
            ),
        )

    return [RepoTarget(package_id=str(r.package_id), repo_url=r.repo_url) for r in rows]


@router.post("/scan/{application_id}", response_model=ScanResult)
async def scan_application(
    application_id: UUID,
    request: ScanRequest,
    db: Session = Depends(get_db),
) -> ScanResult:
    targets = _load_repo_targets(db, application_id)

    if not request.force_refresh:
        existing_ids = {
            str(row.package_id)
            for row in db.query(models.RepositoryProfile.package_id).all()
        }
        targets = [t for t in targets if t.package_id not in existing_ids] or targets

    engine = RepoIntelligenceEngine(db)
    return await engine.scan_application(str(application_id), targets)


@router.get("/packages/{package_id}/profile", response_model=RepositoryProfileOut)
def get_package_repo_profile(package_id: UUID, db: Session = Depends(get_db)) -> RepositoryProfileOut:
    profile = (
        db.query(models.RepositoryProfile)
        .filter(models.RepositoryProfile.package_id == str(package_id))
        .one_or_none()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="No repository profile found. Run a scan first.")
    return profile


@router.get(
    "/applications/{application_id}/profiles", response_model=List[RepositoryProfileOut]
)
def get_application_repo_profiles(
    application_id: UUID, db: Session = Depends(get_db)
) -> List[RepositoryProfileOut]:
    package_ids = [
        r.package_id
        for r in db.execute(
            text(
                "SELECT package_id FROM application_packages WHERE application_id = :app_id"
            ),
            {"app_id": str(application_id)},
        ).fetchall()
    ]
    profiles = (
        db.query(models.RepositoryProfile)
        .filter(models.RepositoryProfile.package_id.in_([str(p) for p in package_ids]))
        .order_by(models.RepositoryProfile.repo_health_score.desc())
        .all()
    )
    if not profiles:
        raise HTTPException(status_code=404, detail="No repository profiles found. Run a scan first.")
    return profiles


@router.get(
    "/applications/{application_id}/single-points-of-failure",
    response_model=List[SinglePointOfFailure],
)
def get_single_points_of_failure(
    application_id: UUID, db: Session = Depends(get_db)
) -> List[SinglePointOfFailure]:
    package_ids = [
        r.package_id
        for r in db.execute(
            text(
                "SELECT package_id FROM application_packages WHERE application_id = :app_id"
            ),
            {"app_id": str(application_id)},
        ).fetchall()
    ]
    profiles = (
        db.query(models.RepositoryProfile)
        .filter(
            models.RepositoryProfile.package_id.in_([str(p) for p in package_ids]),
            models.RepositoryProfile.bus_factor_score >= BUS_FACTOR_ALERT_THRESHOLD,
        )
        .all()
    )
    return [
        SinglePointOfFailure(
            package_id=p.package_id,
            repo_url=p.repo_url,
            top_contributor_commit_share=(
                float(p.top_contributor_commit_share)
                if p.top_contributor_commit_share is not None
                else None
            ),
            bus_factor_score=float(p.bus_factor_score),
            reason=p.explanation.get("bus_factor_reasoning", ""),
        )
        for p in profiles
    ]

"""
FastAPI routes for Module 5 — Enterprise Dependency Intelligence Engine.
Mounted under /api/v1/enterprise-intelligence in app/main.py.
"""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.enterprise_intelligence import models
from app.modules.enterprise_intelligence.schemas import (
    BlastRadiusOut,
    CriticalClusterOut,
    EnterpriseDependencyProfileOut,
    RecomputeResult,
    SetBusinessCriticalityRequest,
)
from app.modules.enterprise_intelligence.service import EnterpriseDependencyIntelligenceEngine

router = APIRouter(prefix="/api/v1/enterprise-intelligence", tags=["Enterprise Dependency Intelligence"])


@router.post("/recompute", response_model=RecomputeResult)
def recompute(db: Session = Depends(get_db)) -> RecomputeResult:
    """
    Org-wide recompute. Run this after any application's SBOM changes, or
    after Module 3/4 scans complete, so this module's components stay fresh.
    """
    engine = EnterpriseDependencyIntelligenceEngine(db)
    return engine.recompute()


@router.get("/shared-dependencies", response_model=List[EnterpriseDependencyProfileOut])
def get_shared_dependencies(
    min_apps: int = Query(default=2, ge=1),
    db: Session = Depends(get_db),
) -> List[EnterpriseDependencyProfileOut]:
    profiles = (
        db.query(models.EnterpriseDependencyProfile)
        .filter(models.EnterpriseDependencyProfile.application_count >= min_apps)
        .order_by(models.EnterpriseDependencyProfile.concentration_ratio.desc())
        .all()
    )
    return profiles


@router.get("/blast-radius/{package_id}", response_model=BlastRadiusOut)
def get_blast_radius(package_id: UUID, db: Session = Depends(get_db)) -> BlastRadiusOut:
    profile = (
        db.query(models.EnterpriseDependencyProfile)
        .filter(models.EnterpriseDependencyProfile.package_id == str(package_id))
        .one_or_none()
    )
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="No enterprise profile found for this package. Run POST /recompute first.",
        )
    return BlastRadiusOut(
        package_id=package_id,
        blast_radius_app_count=profile.blast_radius_app_count,
        total_applications=profile.total_applications,
        concentration_ratio=float(profile.concentration_ratio),
        affected_application_ids=profile.affected_application_ids,
        reasoning=profile.explanation.get("concentration_reasoning", ""),
    )


@router.get("/critical-clusters", response_model=List[CriticalClusterOut])
def get_critical_clusters(
    top: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[CriticalClusterOut]:
    """
    Packages ranked by centrality_score — the structural single points of
    failure of the whole org dependency graph, not just individual repos.
    """
    profiles = (
        db.query(models.EnterpriseDependencyProfile)
        .order_by(models.EnterpriseDependencyProfile.centrality_score.desc())
        .limit(top)
        .all()
    )
    return [
        CriticalClusterOut(
            package_id=p.package_id,
            centrality_score=float(p.centrality_score),
            concentration_ratio=float(p.concentration_ratio),
            application_count=p.application_count,
            reasoning=p.explanation.get("centrality_reasoning", ""),
        )
        for p in profiles
    ]


@router.get("/enterprise-risk-scores", response_model=List[EnterpriseDependencyProfileOut])
def get_enterprise_risk_scores(
    top: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[EnterpriseDependencyProfileOut]:
    profiles = (
        db.query(models.EnterpriseDependencyProfile)
        .order_by(models.EnterpriseDependencyProfile.enterprise_risk_score.desc())
        .limit(top)
        .all()
    )
    return profiles


@router.put("/applications/{application_id}/business-criticality")
def set_business_criticality(
    application_id: UUID,
    request: SetBusinessCriticalityRequest,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    existing = (
        db.query(models.ApplicationBusinessCriticality)
        .filter_by(application_id=str(application_id))
        .one_or_none()
    )
    if existing:
        existing.criticality_level = request.criticality_level.value
    else:
        db.add(
            models.ApplicationBusinessCriticality(
                application_id=str(application_id),
                criticality_level=request.criticality_level.value,
            )
        )
    db.commit()
    return {
        "application_id": str(application_id),
        "criticality_level": request.criticality_level.value,
        "note": "Run POST /recompute to reflect this in enterprise risk scores.",
    }

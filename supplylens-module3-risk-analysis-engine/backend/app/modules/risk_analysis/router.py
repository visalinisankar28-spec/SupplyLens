"""
FastAPI routes for the Risk Analysis Engine (Module 3).
Mounted under /api/v1/risk-analysis in app/main.py.
"""
from __future__ import annotations

from collections import Counter
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.risk_analysis import models
from app.modules.risk_analysis.schemas import (
    ApplicationRiskSummary,
    PackageRiskProfileOut,
    PackageVulnerabilityOut,
    ScanRequest,
    ScanResult,
)
from app.modules.risk_analysis.service import RiskAnalysisEngine, ResolvedPackage

router = APIRouter(prefix="/api/v1/risk-analysis", tags=["Risk Analysis"])


def _load_resolved_packages(db: Session, application_id: UUID) -> List[ResolvedPackage]:
    """
    Bridges to Module 1/2's schema: pulls every package resolved for this
    application's dependency graph. Adjust the SQL below if Module 1/2's
    actual table/column names differ from the assumed `packages` /
    `application_packages` join table.
    """
    rows = db.execute(
        text(
            """
            SELECT p.id, p.name, p.version, p.ecosystem, p.license_id
            FROM packages p
            JOIN application_packages ap ON ap.package_id = p.id
            WHERE ap.application_id = :app_id
            """
        ),
        {"app_id": str(application_id)},
    ).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                "No resolved packages found for this application. "
                "Run the SBOM Parser (Module 1) and Dependency Graph Engine "
                "(Module 2) for this application before scanning."
            ),
        )

    return [
        ResolvedPackage(
            package_id=str(r.id),
            name=r.name,
            version=r.version,
            ecosystem=r.ecosystem,
            license_id=r.license_id,
        )
        for r in rows
    ]


@router.post("/scan/{application_id}", response_model=ScanResult)
async def scan_application(
    application_id: UUID,
    request: ScanRequest,
    db: Session = Depends(get_db),
) -> ScanResult:
    """Run vulnerability + license analysis for every package in an application."""
    packages = _load_resolved_packages(db, application_id)

    if not request.force_refresh:
        # Skip packages we already have a same-day profile for, to reduce
        # unnecessary OSV calls. Kept simple/explicit for readability.
        existing_ids = {
            str(row.package_id)
            for row in db.query(models.PackageRiskProfile.package_id)
            .filter(models.PackageRiskProfile.application_id == str(application_id))
            .all()
        }
        packages = [p for p in packages if p.package_id not in existing_ids] or packages

    engine = RiskAnalysisEngine(db)
    result = await engine.scan_application(str(application_id), packages)
    return result


@router.get("/applications/{application_id}/profile", response_model=List[PackageRiskProfileOut])
def get_application_risk_profile(
    application_id: UUID, db: Session = Depends(get_db)
) -> List[PackageRiskProfileOut]:
    profiles = (
        db.query(models.PackageRiskProfile)
        .filter(models.PackageRiskProfile.application_id == str(application_id))
        .order_by(models.PackageRiskProfile.vulnerability_score.desc())
        .all()
    )
    if not profiles:
        raise HTTPException(status_code=404, detail="No risk profile found. Run a scan first.")
    return profiles


@router.get("/packages/{package_id}/vulnerabilities", response_model=List[PackageVulnerabilityOut])
def get_package_vulnerabilities(
    package_id: UUID, db: Session = Depends(get_db)
) -> List[PackageVulnerabilityOut]:
    links = (
        db.query(models.PackageVulnerability)
        .filter(models.PackageVulnerability.package_id == str(package_id))
        .all()
    )
    return links


@router.get("/applications/{application_id}/summary", response_model=ApplicationRiskSummary)
def get_application_risk_summary(
    application_id: UUID, db: Session = Depends(get_db)
) -> ApplicationRiskSummary:
    profiles = (
        db.query(models.PackageRiskProfile)
        .filter(models.PackageRiskProfile.application_id == str(application_id))
        .all()
    )
    if not profiles:
        raise HTTPException(status_code=404, detail="No risk profile found. Run a scan first.")

    severity_counts: Counter[str] = Counter()
    license_denied = 0
    license_review = 0
    unpatchable = 0

    for p in profiles:
        score = float(p.vulnerability_score)
        if score >= 9.0:
            severity_counts["critical"] += 1
        elif score >= 7.0:
            severity_counts["high"] += 1
        elif score >= 4.0:
            severity_counts["medium"] += 1
        elif score > 0:
            severity_counts["low"] += 1
        else:
            severity_counts["clean"] += 1

        if p.license_policy_status == "DENIED":
            license_denied += 1
        elif p.license_policy_status == "REVIEW":
            license_review += 1

        if float(p.patch_gap_score) >= 10.0:
            unpatchable += 1

    return ApplicationRiskSummary(
        application_id=application_id,
        total_packages=len(profiles),
        critical_count=severity_counts["critical"],
        high_count=severity_counts["high"],
        medium_count=severity_counts["medium"],
        low_count=severity_counts["low"],
        clean_count=severity_counts["clean"],
        license_denied_count=license_denied,
        license_review_count=license_review,
        unpatchable_count=unpatchable,
    )

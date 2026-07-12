"""
Business logic for Governance Reporting.

This module only reads and ranks data produced by earlier modules
(Risk Analysis Engine, Repository Intelligence Engine, Enterprise
Dependency Intelligence Engine). It intentionally contains no ML /
black-box scoring — every number here is either a stored value or a
documented, auditable formula (see README_MODULE6.md, section 5).

Queries use SQLAlchemy Core `text()` against the schema assumed to exist
from Modules 1-5. Swap the raw SQL for your actual ORM models if Modules
1-5 expose them — the function signatures / return shapes are the
contract the router and frontend depend on, not the query style.
"""

from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.governance.schemas import (
    ExportPdfResponse,
    GovernanceSummary,
    RemediationItem,
    RemediationPriorityResponse,
    ReportHistoryItem,
    RiskBucket,
    RiskDistributionBucket,
    RiskyApplication,
    RiskyDependency,
    SharedDependency,
)
from app.modules.governance.pdf_report import build_executive_pdf

REPORTS_DIR = Path("storage/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _bucket_for(score: float) -> RiskBucket:
    """Fixed thresholds so 'Critical' means the same thing every run."""
    if score >= 90:
        return RiskBucket.CRITICAL
    if score >= 70:
        return RiskBucket.HIGH
    if score >= 40:
        return RiskBucket.MEDIUM
    return RiskBucket.LOW


async def get_summary(db: AsyncSession) -> GovernanceSummary:
    apps = (
        await db.execute(
            text(
                """
                SELECT a.id, ers.score
                FROM applications a
                JOIN enterprise_risk_scores ers ON ers.application_id = a.id
                """
            )
        )
    ).all()

    dep_count = (await db.execute(text("SELECT COUNT(*) FROM dependencies"))).scalar_one()
    shared_count = (
        await db.execute(text("SELECT COUNT(*) FROM shared_dependencies WHERE application_count > 1"))
    ).scalar_one()
    open_vulns = (
        await db.execute(
            text("SELECT COUNT(*) FROM vulnerabilities WHERE patch_available = false")
        )
    ).scalar_one()

    scores = [row.score for row in apps]
    total_apps = len(scores)
    avg_score = round(statistics.fmean(scores), 2) if scores else 0.0
    median_score = round(statistics.median(scores), 2) if scores else 0.0

    bucket_counts: dict[RiskBucket, int] = {b: 0 for b in RiskBucket}
    for s in scores:
        bucket_counts[_bucket_for(s)] += 1

    distribution = [
        RiskDistributionBucket(
            bucket=b,
            count=bucket_counts[b],
            percentage=round((bucket_counts[b] / total_apps) * 100, 1) if total_apps else 0.0,
        )
        for b in RiskBucket
    ]

    return GovernanceSummary(
        total_applications=total_apps,
        total_dependencies=dep_count,
        total_shared_dependencies=shared_count,
        total_open_vulnerabilities=open_vulns,
        average_risk_score=avg_score,
        median_risk_score=median_score,
        critical_application_count=bucket_counts[RiskBucket.CRITICAL],
        distribution=distribution,
        generated_at=datetime.now(timezone.utc),
    )


async def get_top_risky_applications(db: AsyncSession, limit: int = 10) -> list[RiskyApplication]:
    rows = (
        await db.execute(
            text(
                """
                SELECT a.id AS application_id,
                       a.name AS application_name,
                       a.business_criticality,
                       a.owner_team,
                       ers.score AS risk_score,
                       ers.blast_radius,
                       ers.spof_count
                FROM applications a
                JOIN enterprise_risk_scores ers ON ers.application_id = a.id
                ORDER BY ers.score DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()

    return [RiskyApplication(**row) for row in rows]


async def get_top_risky_dependencies(db: AsyncSession, limit: int = 10) -> list[RiskyDependency]:
    rows = (
        await db.execute(
            text(
                """
                SELECT d.id AS dependency_id,
                       d.name AS dependency_name,
                       d.ecosystem,
                       drs.final_score AS risk_score,
                       COALESCE(v.max_cvss, 0) AS max_cvss,
                       COALESCE(v.has_patch, false) AS patch_available,
                       rh.scorecard_score AS repo_health_score,
                       COALESCE(sd.application_count, 0) AS affected_application_count
                FROM dependencies d
                JOIN dependency_risk_scores drs ON drs.dependency_id = d.id
                LEFT JOIN repository_health rh ON rh.dependency_id = d.id
                LEFT JOIN shared_dependencies sd ON sd.dependency_id = d.id
                LEFT JOIN (
                    SELECT dependency_id,
                           MAX(cvss_score) AS max_cvss,
                           BOOL_OR(patch_available) AS has_patch
                    FROM vulnerabilities
                    GROUP BY dependency_id
                ) v ON v.dependency_id = d.id
                ORDER BY drs.final_score DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()

    return [RiskyDependency(**row) for row in rows]


async def get_top_shared_dependencies(db: AsyncSession, limit: int = 10) -> list[SharedDependency]:
    total_apps = (await db.execute(text("SELECT COUNT(*) FROM applications"))).scalar_one() or 1

    rows = (
        await db.execute(
            text(
                """
                SELECT d.id AS dependency_id,
                       d.name AS dependency_name,
                       d.ecosystem,
                       sd.application_count,
                       ARRAY(
                           SELECT a.name FROM applications a
                           WHERE a.id = ANY(sd.application_ids)
                       ) AS application_names
                FROM shared_dependencies sd
                JOIN dependencies d ON d.id = sd.dependency_id
                ORDER BY sd.application_count DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()

    return [
        SharedDependency(
            **row,
            concentration_ratio=round(row["application_count"] / total_apps, 3),
        )
        for row in rows
    ]


def _normalize(values: list[float]) -> list[float]:
    """Min-max scale to [0, 1]; returns all zeros if the range is degenerate."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


async def get_remediation_priority(
    db: AsyncSession, limit: int = 25
) -> RemediationPriorityResponse:
    """
    Builds the single ranked worklist a security team should work through.

    Weighted formula (documented in README_MODULE6.md §5.1):
        priority = 0.35 * risk_score
                 + 0.30 * affected_application_count   (blast radius proxy)
                 + 0.20 * max_cvss
                 + 0.15 * patch_penalty
    All four inputs are min-max normalized against the candidate set before
    weighting so the score stays comparable and explainable.
    """
    rows = (
        await db.execute(
            text(
                """
                SELECT dependency_id, dependency_name, ecosystem,
                       risk_score, affected_application_count, max_cvss,
                       patch_available, repo_health_score, is_maintained
                FROM remediation_priority_view
                """
            )
        )
    ).mappings().all()

    if not rows:
        return RemediationPriorityResponse(
            generated_at=datetime.now(timezone.utc), items=[]
        )

    risk_norm = _normalize([r["risk_score"] or 0 for r in rows])
    blast_norm = _normalize([r["affected_application_count"] or 0 for r in rows])
    cvss_norm = _normalize([r["max_cvss"] or 0 for r in rows])

    scored = []
    for row, rn, bn, cn in zip(rows, risk_norm, blast_norm, cvss_norm):
        patch_penalty = 0.0 if row["patch_available"] else 1.0
        priority_score = round(
            0.35 * rn + 0.30 * bn + 0.20 * cn + 0.15 * patch_penalty, 4
        )
        scored.append((priority_score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[:limit]

    items: list[RemediationItem] = []
    for rank, (priority_score, row) in enumerate(top, start=1):
        patch_note = "no patch available" if not row["patch_available"] else "patch available"
        explanation = (
            f"CVSS {row['max_cvss']:.1f}, {patch_note}, "
            f"used by {row['affected_application_count']} application(s)."
        )
        items.append(
            RemediationItem(
                rank=rank,
                dependency_id=row["dependency_id"],
                dependency_name=row["dependency_name"],
                priority_score=priority_score,
                risk_score=row["risk_score"],
                affected_application_count=row["affected_application_count"],
                max_cvss=row["max_cvss"],
                patch_available=row["patch_available"],
                is_maintained=row["is_maintained"],
                explanation=explanation,
            )
        )

    return RemediationPriorityResponse(
        generated_at=datetime.now(timezone.utc), items=items
    )


async def refresh_remediation_view(db: AsyncSession) -> None:
    """Call after every SBOM ingest / on a nightly schedule."""
    await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY remediation_priority_view"))
    await db.commit()


async def create_pdf_export(
    db: AsyncSession,
    requested_by: str,
    report_type: str = "executive_summary",
    application_ids: Optional[list[uuid.UUID]] = None,
) -> ExportPdfResponse:
    summary = await get_summary(db)
    top_apps = await get_top_risky_applications(db, limit=10)
    top_deps = await get_top_risky_dependencies(db, limit=10)
    shared = await get_top_shared_dependencies(db, limit=10)
    remediation = await get_remediation_priority(db, limit=25)

    report_id = uuid.uuid4()
    file_path = REPORTS_DIR / f"{report_id}.pdf"

    build_executive_pdf(
        output_path=file_path,
        summary=summary,
        top_applications=top_apps,
        top_dependencies=top_deps,
        top_shared=shared,
        remediation=remediation,
    )

    await db.execute(
        text(
            """
            INSERT INTO report_exports (id, report_type, generated_by, file_path, filters_json)
            VALUES (:id, :report_type, :generated_by, :file_path, :filters_json)
            """
        ),
        {
            "id": report_id,
            "report_type": report_type,
            "generated_by": requested_by,
            "file_path": str(file_path),
            "filters_json": "{}" if not application_ids else str({"application_ids": [str(a) for a in application_ids]}),
        },
    )
    await db.commit()

    return ExportPdfResponse(
        report_id=report_id,
        status="completed",
        download_url=f"/api/v1/governance/export/{report_id}/download",
    )


async def get_report_file_path(db: AsyncSession, report_id: uuid.UUID) -> Optional[Path]:
    row = (
        await db.execute(
            text("SELECT file_path FROM report_exports WHERE id = :id"),
            {"id": report_id},
        )
    ).mappings().first()
    if not row:
        return None
    return Path(row["file_path"])


async def get_report_history(db: AsyncSession, limit: int = 20) -> list[ReportHistoryItem]:
    rows = (
        await db.execute(
            text(
                """
                SELECT id AS report_id, report_type, generated_by, created_at
                FROM report_exports
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
    ).mappings().all()

    return [
        ReportHistoryItem(
            **row,
            download_url=f"/api/v1/governance/export/{row['report_id']}/download",
        )
        for row in rows
    ]

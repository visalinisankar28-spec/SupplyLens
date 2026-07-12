"""
FastAPI routes for Governance Reporting.

Mounted in app/main.py with:
    app.include_router(governance_router, prefix="/api/v1/governance", tags=["Governance"])
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db  # existing dependency from Modules 1-5
from app.modules.governance import service
from app.modules.governance.schemas import (
    ExportPdfRequest,
    ExportPdfResponse,
    GovernanceSummary,
    RemediationPriorityResponse,
    ReportHistoryItem,
    RiskyApplication,
    RiskyDependency,
    SharedDependency,
)

router = APIRouter()


@router.get("/summary", response_model=GovernanceSummary)
async def governance_summary(db: AsyncSession = Depends(get_db)) -> GovernanceSummary:
    return await service.get_summary(db)


@router.get("/top-risky-applications", response_model=list[RiskyApplication])
async def top_risky_applications(
    limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[RiskyApplication]:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return await service.get_top_risky_applications(db, limit=limit)


@router.get("/top-risky-dependencies", response_model=list[RiskyDependency])
async def top_risky_dependencies(
    limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[RiskyDependency]:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return await service.get_top_risky_dependencies(db, limit=limit)


@router.get("/top-shared-dependencies", response_model=list[SharedDependency])
async def top_shared_dependencies(
    limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[SharedDependency]:
    if not 1 <= limit <= 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    return await service.get_top_shared_dependencies(db, limit=limit)


@router.get("/remediation-priority", response_model=RemediationPriorityResponse)
async def remediation_priority(
    limit: int = 25, db: AsyncSession = Depends(get_db)
) -> RemediationPriorityResponse:
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 200")
    return await service.get_remediation_priority(db, limit=limit)


@router.post("/export/pdf", response_model=ExportPdfResponse, status_code=201)
async def export_pdf(
    payload: ExportPdfRequest, db: AsyncSession = Depends(get_db)
) -> ExportPdfResponse:
    return await service.create_pdf_export(
        db,
        requested_by=payload.requested_by,
        report_type=payload.report_type,
        application_ids=payload.application_ids,
    )


@router.get("/export/{report_id}/download")
async def download_report(report_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    file_path = await service.get_report_file_path(db, report_id)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"supplylens-executive-report-{report_id}.pdf",
    )


@router.get("/export/history", response_model=list[ReportHistoryItem])
async def export_history(
    limit: int = 20, db: AsyncSession = Depends(get_db)
) -> list[ReportHistoryItem]:
    return await service.get_report_history(db, limit=limit)

"""SBOM upload/retrieval endpoints."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.sbom import Application, SBOMDocument
from app.schemas.api import SBOMDocumentDetail, SBOMUploadResponse
from app.services.sbom_ingestion_service import (
    SBOMIngestionError,
    parse_raw_sbom,
    persist_parsed_sbom,
)
from app.services.sbom_parser.base import SBOMParseError

router = APIRouter(prefix="/api/v1/sbom", tags=["sbom"])

_MAX_UPLOAD_BYTES = settings.max_sbom_upload_size_mb * 1024 * 1024


@router.post("/upload", response_model=SBOMUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_sbom(
    application_id: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
) -> SBOMUploadResponse:
    """Upload a CycloneDX or SPDX JSON SBOM for a given application.

    The endpoint auto-detects the format — callers don't need to specify it.
    """
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")

    contents = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"SBOM exceeds max upload size of {settings.max_sbom_upload_size_mb} MB",
        )

    try:
        raw = json.loads(contents)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"Uploaded file is not valid JSON: {exc}") from exc

    try:
        parsed = parse_raw_sbom(raw)
    except SBOMParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SBOMIngestionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    document = persist_parsed_sbom(
        db=db,
        application_id=application_id,
        parsed=parsed,
        raw_metadata={"original_filename": file.filename},
    )

    direct_count = sum(1 for c in document.components if c.is_direct)
    return SBOMUploadResponse(
        sbom_document_id=document.id,
        application_id=application_id,
        format=parsed.format,
        spec_version=parsed.spec_version,
        component_count=len(document.components),
        direct_dependency_count=direct_count,
        edge_count=len(document.edges),
        warnings=parsed.warnings,
    )


@router.get("/{sbom_document_id}", response_model=SBOMDocumentDetail)
def get_sbom_document(sbom_document_id: uuid.UUID, db: Session = Depends(get_db)) -> SBOMDocument:
    document = db.get(SBOMDocument, sbom_document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="SBOM document not found")
    return document

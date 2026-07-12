"""Request/response contracts for the SBOM API — deliberately separate from
`sbom.py`'s internal ParsedSBOM shape. The API contract and the internal
parser contract are allowed to evolve independently."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel

from app.schemas.sbom import ComponentType, SBOMFormat


class SBOMUploadResponse(BaseModel):
    sbom_document_id: uuid.UUID
    application_id: uuid.UUID
    format: SBOMFormat
    spec_version: str | None
    component_count: int
    direct_dependency_count: int
    edge_count: int
    warnings: list[str]


class ComponentOut(BaseModel):
    id: uuid.UUID
    ref: str
    name: str
    version: str | None
    purl: str | None
    ecosystem: str | None
    license: str | None
    component_type: ComponentType
    is_direct: bool
    source_repo_url: str | None

    class Config:
        from_attributes = True


class SBOMDocumentDetail(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    format: SBOMFormat
    spec_version: str | None
    root_component_ref: str | None
    uploaded_at: datetime.datetime
    parse_warnings: list[str] | None
    components: list[ComponentOut]

    class Config:
        from_attributes = True

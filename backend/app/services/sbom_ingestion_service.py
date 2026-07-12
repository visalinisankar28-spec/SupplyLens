"""
Ties the format-agnostic parser output to the persistence layer.

This is intentionally the ONLY place that knows both "how to parse" and
"how to store" — routes never touch SQLAlchemy models directly, and
parsers never touch the database. That separation is what makes Module 1
testable without a running Postgres instance (see tests/).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.sbom import (
    Component,
    ComponentTypeEnum,
    DependencyEdge,
    SBOMDocument,
    SBOMFormatEnum,
)
from app.schemas.sbom import ParsedSBOM
from app.services.sbom_parser.base import SBOMParseError
from app.services.sbom_parser.factory import get_parser_for


class SBOMIngestionError(Exception):
    pass


def parse_raw_sbom(raw: dict[str, Any]) -> ParsedSBOM:
    """Pure function: raw JSON in, normalized ParsedSBOM out. No DB access —
    kept separate so unit tests can call this without a database at all."""
    parser = get_parser_for(raw)
    try:
        return parser.parse(raw)
    except SBOMParseError:
        raise
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any parser
        # bug must surface as a clean ingestion error, never a raw 500.
        raise SBOMParseError(f"Failed to parse SBOM: {exc}") from exc


def persist_parsed_sbom(
    db: Session,
    application_id: uuid.UUID,
    parsed: ParsedSBOM,
    raw_metadata: dict[str, Any] | None = None,
) -> SBOMDocument:
    """Writes a ParsedSBOM and all its components/edges to the database in
    one transaction. Returns the persisted SBOMDocument (with relationships
    populated) so the API layer can build its response from it directly."""

    document = SBOMDocument(
        application_id=application_id,
        format=SBOMFormatEnum(parsed.format.value),
        spec_version=parsed.spec_version,
        root_component_ref=parsed.root_component_ref,
        raw_metadata=raw_metadata,
        parse_warnings=parsed.warnings,
    )
    db.add(document)
    db.flush()  # assigns document.id without committing yet

    for comp in parsed.components:
        db.add(
            Component(
                sbom_document_id=document.id,
                ref=comp.ref,
                name=comp.name,
                version=comp.version,
                purl=comp.purl,
                ecosystem=comp.ecosystem,
                license=comp.license,
                component_type=ComponentTypeEnum(comp.component_type.value),
                is_direct=comp.is_direct,
                source_repo_url=comp.source_repo_url,
            )
        )

    for edge in parsed.edges:
        db.add(
            DependencyEdge(
                sbom_document_id=document.id,
                source_ref=edge.source_ref,
                target_ref=edge.target_ref,
            )
        )

    db.commit()
    db.refresh(document)
    return document

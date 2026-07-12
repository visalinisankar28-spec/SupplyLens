"""
Persistence schema for Module 1.

Design notes:
- `Component` rows are scoped to a single `SBOMDocument` (component_id is
  NOT globally unique across applications). Cross-application identity —
  "is this the same lodash@4.17.15 as in app B" — is resolved later by the
  Enterprise Dependency Intelligence Engine (Module 5) via `purl`, not here.
  Module 1's job is faithful extraction, not cross-app correlation.
- `DependencyEdge` stores refs as they appeared in the source SBOM
  (bom-ref / SPDXID), not database IDs, until the Dependency Graph Engine
  (Module 2) resolves them into an actual NetworkX graph. We keep the
  raw component_id foreign keys too, resolved at parse-time, so Module 2
  doesn't have to re-parse strings.
"""

from __future__ import annotations

import datetime
import enum
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SBOMFormatEnum(str, enum.Enum):
    CYCLONEDX = "cyclonedx"
    SPDX = "spdx"


class ComponentTypeEnum(str, enum.Enum):
    LIBRARY = "library"
    APPLICATION = "application"
    FRAMEWORK = "framework"
    UNKNOWN = "unknown"


class Application(Base):
    """A business application in the org's portfolio (seeded from
    applications.json in the hackathon dataset; in production this would
    sync from a CMDB)."""

    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    business_criticality: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)

    sbom_documents: Mapped[list["SBOMDocument"]] = relationship(back_populates="application")


class SBOMDocument(Base):
    """One uploaded SBOM, tied to exactly one application. An application
    can have multiple SBOM uploads over time (we keep history)."""

    __tablename__ = "sbom_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"), nullable=False)
    format: Mapped[SBOMFormatEnum] = mapped_column(Enum(SBOMFormatEnum), nullable=False)
    spec_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    root_component_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, nullable=False
    )
    raw_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parse_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    application: Mapped["Application"] = relationship(back_populates="sbom_documents")
    components: Mapped[list["Component"]] = relationship(
        back_populates="sbom_document", cascade="all, delete-orphan"
    )
    edges: Mapped[list["DependencyEdge"]] = relationship(
        back_populates="sbom_document", cascade="all, delete-orphan"
    )


class Component(Base):
    """A single component (library/package version) extracted from one
    SBOM document."""

    __tablename__ = "components"
    __table_args__ = (
        UniqueConstraint("sbom_document_id", "ref", name="uq_component_ref_per_sbom"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sbom_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sbom_documents.id"), nullable=False
    )
    ref: Mapped[str] = mapped_column(String(500), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purl: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    ecosystem: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    component_type: Mapped[ComponentTypeEnum] = mapped_column(
        Enum(ComponentTypeEnum), nullable=False, default=ComponentTypeEnum.UNKNOWN
    )
    is_direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_repo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    sbom_document: Mapped["SBOMDocument"] = relationship(back_populates="components")


class DependencyEdge(Base):
    """A directed edge: source component depends on target component,
    within one SBOM document."""

    __tablename__ = "dependency_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sbom_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sbom_documents.id"), nullable=False
    )
    source_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(500), nullable=False)

    sbom_document: Mapped["SBOMDocument"] = relationship(back_populates="edges")

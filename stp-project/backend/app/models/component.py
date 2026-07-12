"""
Component model.

NOTE: This table is owned conceptually by Module 1 (SBOM Ingestion & Parsing).
It is redefined here with the minimal fields Module 2 depends on so this
module can be developed and tested independently. When Module 1 is merged,
replace this file with an import of the real model - do not duplicate the
table definition in both places.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Component(Base):
    """A single software component extracted from an SBOM."""

    __tablename__ = "components"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sbom_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    # Package URL - the canonical, ecosystem-agnostic identifier (e.g.
    # "pkg:npm/left-pad@1.3.0"). This is what every downstream module keys on.
    purl: Mapped[str] = mapped_column(String(512), unique=True, index=True)

    name: Mapped[str] = mapped_column(String(256))
    version: Mapped[str] = mapped_column(String(128))
    ecosystem: Mapped[str] = mapped_column(String(64))  # npm | pypi | maven | ...

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    health_profile: Mapped["DependencyHealthProfile | None"] = relationship(
        back_populates="component", uselist=False, cascade="all, delete-orphan"
    )

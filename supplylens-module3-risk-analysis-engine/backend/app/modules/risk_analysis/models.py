"""
SQLAlchemy ORM models for the Risk Analysis Engine (Module 3).

These tables extend the schema owned by Module 1 (packages) and
Module 2 (applications / dependency graph). They do not redefine
those tables — only reference them via foreign keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class Vulnerability(Base):
    """A single vulnerability record, cached locally from OSV."""

    __tablename__ = "vulnerabilities"
    __table_args__ = (UniqueConstraint("vuln_id", "source", name="uq_vuln_source"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vuln_id = Column(String(64), nullable=False, index=True)  # e.g. GHSA-xxxx, CVE-2023-xxxx
    source = Column(String(32), nullable=False, default="OSV")
    summary = Column(Text, nullable=True)
    cvss_score = Column(Numeric(3, 1), nullable=True)
    cvss_vector = Column(String(128), nullable=True)
    severity = Column(String(16), nullable=True)  # LOW / MEDIUM / HIGH / CRITICAL
    published_at = Column(DateTime, nullable=True)
    raw_payload = Column(JSONB, nullable=True)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    package_links = relationship(
        "PackageVulnerability", back_populates="vulnerability", cascade="all, delete-orphan"
    )


class PackageVulnerability(Base):
    """Join table: which package/version is affected by which vulnerability."""

    __tablename__ = "package_vulnerabilities"
    __table_args__ = (
        UniqueConstraint("package_id", "vulnerability_id", name="uq_package_vuln"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    vulnerability_id = Column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False
    )
    affected_version = Column(String(64), nullable=False)
    fixed_version = Column(String(64), nullable=True)
    is_patch_available = Column(Boolean, nullable=False, default=False)
    versions_behind_fix = Column(Integer, nullable=True)

    vulnerability = relationship("Vulnerability", back_populates="package_links")


class PackageRiskProfile(Base):
    """
    Explainable, recomputable risk snapshot for a package inside the
    context of a specific application. One row per (package, application)
    per scan.
    """

    __tablename__ = "package_risk_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    application_id = Column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )

    vulnerability_score = Column(Numeric(4, 2), nullable=False, default=0)
    patch_gap_score = Column(Numeric(4, 2), nullable=False, default=0)
    license_risk_score = Column(Numeric(4, 2), nullable=False, default=0)

    license_id = Column(String(64), nullable=True)
    license_policy_status = Column(String(16), nullable=True)  # ALLOWED/REVIEW/DENIED/UNKNOWN

    explanation = Column(JSONB, nullable=False, default=dict)
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

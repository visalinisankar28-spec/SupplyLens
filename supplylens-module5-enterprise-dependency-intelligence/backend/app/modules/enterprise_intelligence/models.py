"""
SQLAlchemy ORM models for the Enterprise Dependency Intelligence Engine
(Module 5) — the org-wide correlation layer that is SupplyLens's core
differentiator.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class ApplicationBusinessCriticality(Base):
    """Governance input: how critical is this application to the business."""

    __tablename__ = "application_business_criticality"

    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        primary_key=True,
    )
    criticality_level = Column(String(16), nullable=False, default="MEDIUM")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class EnterpriseDependencyProfile(Base):
    """
    One row per package, computed ORG-WIDE across every application —
    not per-application like Module 3/4's profiles. This is the table the
    Governance Dashboard (Module 6) reads from for cross-app intelligence.
    """

    __tablename__ = "enterprise_dependency_profiles"
    __table_args__ = (UniqueConstraint("package_id", name="uq_enterprise_profile_package"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)

    application_count = Column(Integer, nullable=False)
    total_applications = Column(Integer, nullable=False)
    concentration_ratio = Column(Numeric(5, 4), nullable=False)

    betweenness_centrality = Column(Numeric(8, 6), nullable=True)
    centrality_score = Column(Numeric(4, 2), nullable=False, default=0)

    blast_radius_app_count = Column(Integer, nullable=False)
    affected_application_ids = Column(JSONB, nullable=False, default=list)

    business_criticality_score = Column(Numeric(4, 2), nullable=False, default=0)

    vulnerability_component = Column(Numeric(4, 2), nullable=False, default=0)
    repo_health_component = Column(Numeric(4, 2), nullable=False, default=0)
    license_component = Column(Numeric(4, 2), nullable=False, default=0)

    enterprise_risk_score = Column(Numeric(4, 2), nullable=False, default=0)
    explanation = Column(JSONB, nullable=False, default=dict)
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

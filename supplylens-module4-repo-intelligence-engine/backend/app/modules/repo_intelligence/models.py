"""
SQLAlchemy ORM model for the Repository & Maintenance Intelligence Engine
(Module 4). Extends the `packages` table owned by Module 1.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class RepositoryProfile(Base):
    """One row per package: the health profile of its upstream repository."""

    __tablename__ = "repository_profiles"
    __table_args__ = (UniqueConstraint("package_id", name="uq_repo_profile_package"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)

    repo_url = Column(Text, nullable=False)
    repo_platform = Column(String(32), nullable=False, default="github")

    stars = Column(Integer, nullable=True)
    forks = Column(Integer, nullable=True)
    open_issues = Column(Integer, nullable=True)
    contributors_count = Column(Integer, nullable=True)

    last_commit_at = Column(DateTime, nullable=True)
    last_release_at = Column(DateTime, nullable=True)
    release_count_last_year = Column(Integer, nullable=True)

    top_contributor_commit_share = Column(Numeric(5, 2), nullable=True)  # 0-100 (%)

    scorecard_overall_score = Column(Numeric(3, 1), nullable=True)  # 0-10
    scorecard_checks = Column(JSONB, nullable=True)

    maintenance_score = Column(Numeric(4, 2), nullable=False, default=0)
    activity_score = Column(Numeric(4, 2), nullable=False, default=0)
    bus_factor_score = Column(Numeric(4, 2), nullable=False, default=0)
    repo_health_score = Column(Numeric(4, 2), nullable=False, default=0)

    explanation = Column(JSONB, nullable=False, default=dict)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)

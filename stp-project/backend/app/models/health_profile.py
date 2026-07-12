"""
DependencyHealthProfile model.

Stores the raw signals collected from external sources (OpenSSF Scorecard,
package registries) alongside the computed Dependency Health Index (DHI),
so that expensive external API calls are made once per component per
analysis run, not on every dashboard page load.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class HealthCategory(str, enum.Enum):
    """Human-readable classification bucket for a component's DHI score."""

    HEALTHY = "Healthy"
    STABLE = "Stable"
    NEEDS_ATTENTION = "Needs Attention"
    HIGH_MAINTENANCE_RISK = "High Maintenance Risk"


class DependencyHealthProfile(Base):
    """Computed health profile for a single component."""

    __tablename__ = "dependency_health_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("components.id", ondelete="CASCADE"), unique=True, index=True
    )

    # --- Resolved repository ---
    repo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    repo_resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Raw signals (kept for transparency / audit, not just the derived score) ---
    scorecard_overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scorecard_maintained_check: Mapped[float | None] = mapped_column(Float, nullable=True)
    scorecard_raw_checks: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    contributors_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    days_since_last_release: Mapped[int | None] = mapped_column(Integer, nullable=True)
    days_since_last_commit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Derived output ---
    maintenance_activity_score: Mapped[float] = mapped_column(Float, default=0.0)
    release_cadence_score: Mapped[float] = mapped_column(Float, default=0.0)
    community_resilience_score: Mapped[float] = mapped_column(Float, default=0.0)
    security_hygiene_score: Mapped[float] = mapped_column(Float, default=0.0)

    dhi_score: Mapped[float] = mapped_column(Float, default=0.0)
    dhi_category: Mapped[HealthCategory] = mapped_column(
        Enum(HealthCategory), default=HealthCategory.NEEDS_ATTENTION
    )
    # Short, ranked list of the factors that most influenced the category -
    # this is what the UI shows under "Why this rating?"
    explanation: Mapped[list[str]] = mapped_column(JSONB, default=list)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    component: Mapped["Component"] = relationship(back_populates="health_profile")

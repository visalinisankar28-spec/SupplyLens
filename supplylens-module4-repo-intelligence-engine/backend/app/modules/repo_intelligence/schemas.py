"""Pydantic request/response schemas for Module 4 — Repository Intelligence."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RepositoryProfileOut(BaseModel):
    id: UUID
    package_id: UUID
    repo_url: str
    repo_platform: str

    stars: Optional[int] = None
    forks: Optional[int] = None
    open_issues: Optional[int] = None
    contributors_count: Optional[int] = None

    last_commit_at: Optional[datetime] = None
    last_release_at: Optional[datetime] = None
    release_count_last_year: Optional[int] = None

    top_contributor_commit_share: Optional[float] = None

    scorecard_overall_score: Optional[float] = None
    scorecard_checks: Optional[dict[str, Any]] = None

    maintenance_score: float
    activity_score: float
    bus_factor_score: float
    repo_health_score: float

    explanation: dict[str, Any]
    fetched_at: datetime

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    force_refresh: bool = Field(default=False)


class ScanResult(BaseModel):
    application_id: UUID
    repositories_scanned: int
    profiles_generated: int
    duration_ms: int


class SinglePointOfFailure(BaseModel):
    package_id: UUID
    repo_url: str
    top_contributor_commit_share: Optional[float] = None
    bus_factor_score: float
    reason: str

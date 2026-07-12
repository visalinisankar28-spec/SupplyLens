"""
Pydantic response/request models for the Governance Reporting module.

These models define the contract between the FastAPI routes and the
frontend dashboard. Every field that shows up in the UI or PDF is
represented explicitly here — no ad-hoc dicts crossing the API boundary.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RiskBucket(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class RiskDistributionBucket(BaseModel):
    bucket: RiskBucket
    count: int
    percentage: float = Field(..., description="Share of total applications, 0-100")


class GovernanceSummary(BaseModel):
    """Portfolio-wide snapshot shown at the top of the dashboard."""

    total_applications: int
    total_dependencies: int
    total_shared_dependencies: int
    total_open_vulnerabilities: int
    average_risk_score: float
    median_risk_score: float
    critical_application_count: int
    distribution: list[RiskDistributionBucket]
    generated_at: datetime


class RiskyApplication(BaseModel):
    application_id: UUID
    application_name: str
    business_criticality: str
    risk_score: float
    blast_radius: int = Field(..., description="Number of dependencies reachable from this app")
    spof_count: int = Field(..., description="Single points of failure contributed by this app")
    owner_team: Optional[str] = None


class RiskyDependency(BaseModel):
    dependency_id: UUID
    dependency_name: str
    ecosystem: str
    risk_score: float
    max_cvss: float
    patch_available: bool
    repo_health_score: Optional[float] = None
    affected_application_count: int


class SharedDependency(BaseModel):
    dependency_id: UUID
    dependency_name: str
    ecosystem: str
    application_count: int
    application_names: list[str]
    concentration_ratio: float = Field(
        ..., description="application_count / total_applications, 0-1"
    )


class RemediationItem(BaseModel):
    rank: int
    dependency_id: UUID
    dependency_name: str
    priority_score: float
    risk_score: float
    affected_application_count: int
    max_cvss: float
    patch_available: bool
    is_maintained: Optional[bool] = None
    explanation: str = Field(
        ..., description="Human-readable justification for this ranking"
    )


class RemediationPriorityResponse(BaseModel):
    generated_at: datetime
    items: list[RemediationItem]


class ExportPdfRequest(BaseModel):
    report_type: str = Field(default="executive_summary")
    requested_by: str
    application_ids: Optional[list[UUID]] = Field(
        default=None, description="Optional filter — omit for org-wide report"
    )


class ExportPdfResponse(BaseModel):
    report_id: UUID
    status: str
    download_url: str


class ReportHistoryItem(BaseModel):
    report_id: UUID
    report_type: str
    generated_by: str
    created_at: datetime
    download_url: str

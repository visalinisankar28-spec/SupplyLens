"""
Pydantic request/response schemas for the Risk Analysis Engine (Module 3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VulnerabilityOut(BaseModel):
    id: UUID
    vuln_id: str
    source: str
    summary: Optional[str] = None
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    severity: Optional[str] = None
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PackageVulnerabilityOut(BaseModel):
    package_id: UUID
    vulnerability: VulnerabilityOut
    affected_version: str
    fixed_version: Optional[str] = None
    is_patch_available: bool
    versions_behind_fix: Optional[int] = None

    class Config:
        from_attributes = True


class RiskExplanation(BaseModel):
    """Structured, human-readable breakdown of how a score was derived."""

    worst_vulnerability: Optional[dict[str, Any]] = None
    all_vulnerabilities: list[dict[str, Any]] = Field(default_factory=list)
    patch_reasoning: str
    license_reasoning: str


class PackageRiskProfileOut(BaseModel):
    id: UUID
    package_id: UUID
    application_id: UUID
    vulnerability_score: float
    patch_gap_score: float
    license_risk_score: float
    license_id: Optional[str] = None
    license_policy_status: Optional[str] = None
    explanation: dict[str, Any]
    computed_at: datetime

    class Config:
        from_attributes = True


class ScanRequest(BaseModel):
    force_refresh: bool = Field(
        default=False,
        description="If true, re-fetch OSV data even for packages already cached today.",
    )


class ScanResult(BaseModel):
    application_id: UUID
    packages_scanned: int
    vulnerabilities_found: int
    profiles_generated: int
    duration_ms: int


class ApplicationRiskSummary(BaseModel):
    application_id: UUID
    total_packages: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    clean_count: int
    license_denied_count: int
    license_review_count: int
    unpatchable_count: int

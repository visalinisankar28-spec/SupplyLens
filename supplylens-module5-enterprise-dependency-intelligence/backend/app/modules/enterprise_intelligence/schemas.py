"""Pydantic request/response schemas for Module 5 — Enterprise Dependency Intelligence."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CriticalityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SetBusinessCriticalityRequest(BaseModel):
    criticality_level: CriticalityLevel


class EnterpriseDependencyProfileOut(BaseModel):
    id: UUID
    package_id: UUID

    application_count: int
    total_applications: int
    concentration_ratio: float

    betweenness_centrality: float | None = None
    centrality_score: float

    blast_radius_app_count: int
    affected_application_ids: list[str]

    business_criticality_score: float

    vulnerability_component: float
    repo_health_component: float
    license_component: float

    enterprise_risk_score: float
    explanation: dict[str, Any]
    computed_at: datetime

    class Config:
        from_attributes = True


class RecomputeResult(BaseModel):
    packages_analyzed: int
    total_applications: int
    graph_nodes: int
    graph_edges: int
    duration_ms: int


class BlastRadiusOut(BaseModel):
    package_id: UUID
    blast_radius_app_count: int
    total_applications: int
    concentration_ratio: float
    affected_application_ids: list[str]
    reasoning: str


class CriticalClusterOut(BaseModel):
    package_id: UUID
    centrality_score: float
    concentration_ratio: float
    application_count: int
    reasoning: str

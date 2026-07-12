"""
Router-level tests. The DB dependency (`get_db`) and the service functions
are mocked so these tests exercise request validation, status codes, and
response-shape correctness without needing a live PostgreSQL instance.

Wire an actual Postgres test container in CI for full integration coverage
of the SQL in service.py (see README_MODULE6.md "Testing strategy").
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.modules.governance.router import router as governance_router
from app.modules.governance.schemas import (
    GovernanceSummary,
    RiskBucket,
    RiskDistributionBucket,
)


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(governance_router, prefix="/api/v1/governance")
    test_app.dependency_overrides[get_db] = lambda: AsyncMock()
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


def _fake_summary() -> GovernanceSummary:
    return GovernanceSummary(
        total_applications=20,
        total_dependencies=340,
        total_shared_dependencies=58,
        total_open_vulnerabilities=12,
        average_risk_score=42.3,
        median_risk_score=38.0,
        critical_application_count=2,
        distribution=[
            RiskDistributionBucket(bucket=RiskBucket.LOW, count=8, percentage=40.0),
            RiskDistributionBucket(bucket=RiskBucket.MEDIUM, count=7, percentage=35.0),
            RiskDistributionBucket(bucket=RiskBucket.HIGH, count=3, percentage=15.0),
            RiskDistributionBucket(bucket=RiskBucket.CRITICAL, count=2, percentage=10.0),
        ],
        generated_at=datetime.now(timezone.utc),
    )


def test_summary_returns_200_and_expected_shape(client):
    with patch(
        "app.modules.governance.router.service.get_summary",
        new=AsyncMock(return_value=_fake_summary()),
    ):
        response = client.get("/api/v1/governance/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_applications"] == 20
    assert len(body["distribution"]) == 4


def test_top_risky_applications_rejects_invalid_limit(client):
    response = client.get("/api/v1/governance/top-risky-applications?limit=0")
    assert response.status_code == 400


def test_top_risky_applications_rejects_limit_over_max(client):
    response = client.get("/api/v1/governance/top-risky-applications?limit=500")
    assert response.status_code == 400


def test_export_pdf_returns_download_url(client):
    fake_report_id = uuid4()
    from app.modules.governance.schemas import ExportPdfResponse

    fake_response = ExportPdfResponse(
        report_id=fake_report_id,
        status="completed",
        download_url=f"/api/v1/governance/export/{fake_report_id}/download",
    )
    with patch(
        "app.modules.governance.router.service.create_pdf_export",
        new=AsyncMock(return_value=fake_response),
    ):
        response = client.post(
            "/api/v1/governance/export/pdf",
            json={"report_type": "executive_summary", "requested_by": "security-team"},
        )
    assert response.status_code == 201
    assert response.json()["download_url"].endswith("/download")


def test_download_report_404_when_missing(client):
    with patch(
        "app.modules.governance.router.service.get_report_file_path",
        new=AsyncMock(return_value=None),
    ):
        response = client.get(f"/api/v1/governance/export/{uuid4()}/download")
    assert response.status_code == 404

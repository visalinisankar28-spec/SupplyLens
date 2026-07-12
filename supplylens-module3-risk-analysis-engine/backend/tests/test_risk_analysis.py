"""
Tests for Module 3 — Risk Analysis Engine.

Run with: pytest backend/tests/test_risk_analysis.py -v
"""
from __future__ import annotations

import pytest

from app.modules.risk_analysis.license_compat import (
    LicensePolicyStatus,
    classify_license,
    license_risk_score,
)
from app.modules.risk_analysis.service import (
    _severity_from_cvss,
    _versions_behind,
)


# --------------------------------------------------------------------- #
# License compatibility
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "spdx_id,expected",
    [
        ("MIT", LicensePolicyStatus.ALLOWED),
        ("Apache-2.0", LicensePolicyStatus.ALLOWED),
        ("LGPL-3.0", LicensePolicyStatus.REVIEW),
        ("MPL-2.0", LicensePolicyStatus.REVIEW),
        ("GPL-3.0", LicensePolicyStatus.DENIED),
        ("AGPL-3.0", LicensePolicyStatus.DENIED),
        ("SomeMadeUpLicense-9.9", LicensePolicyStatus.UNKNOWN),
        (None, LicensePolicyStatus.UNKNOWN),
    ],
)
def test_classify_license(spdx_id, expected):
    assert classify_license(spdx_id) == expected


def test_license_risk_score_bands():
    allowed_score, allowed_status, _ = license_risk_score("MIT")
    review_score, review_status, _ = license_risk_score("LGPL-2.1")
    denied_score, denied_status, _ = license_risk_score("AGPL-3.0")

    assert allowed_score == 0.0
    assert review_score == 5.0
    assert denied_score == 10.0
    assert allowed_status == LicensePolicyStatus.ALLOWED
    assert review_status == LicensePolicyStatus.REVIEW
    assert denied_status == LicensePolicyStatus.DENIED


# --------------------------------------------------------------------- #
# Severity mapping
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "cvss,expected",
    [
        (9.8, "CRITICAL"),
        (9.0, "CRITICAL"),
        (8.9, "HIGH"),
        (7.0, "HIGH"),
        (6.9, "MEDIUM"),
        (4.0, "MEDIUM"),
        (3.9, "LOW"),
        (0.0, "LOW"),
        (None, "UNKNOWN"),
    ],
)
def test_severity_from_cvss(cvss, expected):
    assert _severity_from_cvss(cvss) == expected


# --------------------------------------------------------------------- #
# Patch-gap version distance heuristic
# --------------------------------------------------------------------- #

def test_versions_behind_no_gap_when_current_meets_fix():
    assert _versions_behind("2.3.1", "2.3.1") == 0
    assert _versions_behind("2.4.0", "2.3.1") == 0  # already ahead of fix


def test_versions_behind_patch_gap():
    assert _versions_behind("2.3.0", "2.3.1") == 1


def test_versions_behind_minor_gap():
    assert _versions_behind("2.1.0", "2.4.0") == 9  # (4-1)*3


def test_versions_behind_major_gap_weighted_heaviest():
    assert _versions_behind("1.0.0", "2.0.0") == 10  # (2-1)*10
    assert _versions_behind("1.0.0", "3.0.0") == 20


# --------------------------------------------------------------------- #
# Integration-style test with a mocked OSV client
# --------------------------------------------------------------------- #

class _FakeOSVClient:
    """Mocked OSV client returning a fixed, known vulnerability payload."""

    async def query_package(self, package_name, ecosystem, version):
        if package_name == "vulnerable-lib":
            return [
                {
                    "id": "OSV-2024-0001",
                    "summary": "Remote code execution in vulnerable-lib",
                    "severity": [{"type": "CVSS_V3", "score": "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
                    "affected": [
                        {
                            "package": {"name": "vulnerable-lib", "ecosystem": ecosystem},
                            "ranges": [
                                {
                                    "type": "SEMVER",
                                    "events": [{"introduced": "0"}, {"fixed": "2.0.0"}],
                                }
                            ],
                        }
                    ],
                }
            ]
        return []


@pytest.mark.asyncio
async def test_scan_application_builds_risk_profile(db_session):
    """
    Requires a `db_session` pytest fixture (SQLAlchemy session against a
    test database / SQLite) to be provided by conftest.py, along with
    fixture rows for `packages` / `applications` created by Module 1/2's
    own test setup. This test documents the expected contract; wire up
    `conftest.py` fixtures to match your actual Module 1/2 test scaffolding.
    """
    from app.modules.risk_analysis.service import RiskAnalysisEngine, ResolvedPackage

    engine = RiskAnalysisEngine(db_session, osv_client=_FakeOSVClient())
    packages = [
        ResolvedPackage(
            package_id="00000000-0000-0000-0000-000000000001",
            name="vulnerable-lib",
            version="1.0.0",
            ecosystem="PyPI",
            license_id="MIT",
        )
    ]

    result = await engine.scan_application("00000000-0000-0000-0000-0000000000aa", packages)

    assert result.packages_scanned == 1
    assert result.vulnerabilities_found == 1
    assert result.profiles_generated == 1

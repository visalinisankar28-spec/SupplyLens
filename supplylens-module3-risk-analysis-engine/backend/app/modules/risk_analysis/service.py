"""
RiskAnalysisEngine — core algorithms for Module 3.

This service takes packages resolved by Module 1/2, queries OSV for
vulnerabilities, and produces an explainable PackageRiskProfile per
(package, application).

Design principle: every score is a deterministic function of concrete,
citable inputs (a CVSS number, a version diff, a license lookup). No
ML, no black box.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.modules.risk_analysis import models
from app.modules.risk_analysis.license_compat import license_risk_score
from app.modules.risk_analysis.osv_client import OSVClient
from app.modules.risk_analysis.schemas import ScanResult

logger = logging.getLogger(__name__)


@dataclass
class ResolvedPackage:
    """
    Minimal view of a package as needed by this engine. In the real system
    this is produced by Module 1 (SBOM Parser) / Module 2 (Dependency Graph);
    it is declared here as a lightweight contract so this module can be
    developed and tested independently of their internals.
    """

    package_id: str
    name: str
    version: str
    ecosystem: str  # "PyPI", "npm", "Maven", "Go", etc. (SBOM/OSV vocabulary)
    license_id: Optional[str] = None


def _severity_from_cvss(score: Optional[float]) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    return "LOW"


def _parse_semver(version: str) -> tuple[int, ...]:
    """Best-effort semantic version parse; falls back to (0,) on garbage input."""
    cleaned = version.lstrip("v")
    parts: list[int] = []
    for chunk in cleaned.split(".")[:3]:
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def _versions_behind(current: str, fixed: str) -> int:
    """
    Rough 'how many releases behind the fix' heuristic based on semver
    component deltas. Not a precise release-count -- a defensible,
    explainable approximation, which is explicitly documented as a
    known limitation (see README, Future Improvements).
    """
    cur = _parse_semver(current)
    fix = _parse_semver(fixed)
    cur = cur + (0,) * (3 - len(cur))
    fix = fix + (0,) * (3 - len(fix))

    if cur >= fix:
        return 0
    major_gap = max(0, fix[0] - cur[0])
    minor_gap = max(0, fix[1] - cur[1]) if major_gap == 0 else 0
    patch_gap = max(0, fix[2] - cur[2]) if major_gap == 0 and minor_gap == 0 else 0

    if major_gap > 0:
        return major_gap * 10  # crossing a major version is treated as a big gap
    if minor_gap > 0:
        return minor_gap * 3
    return max(patch_gap, 1)


def _extract_cvss(vuln_payload: dict[str, Any]) -> tuple[Optional[float], Optional[str]]:
    """Pull the best available CVSS score/vector out of an OSV vuln record."""
    for severity_entry in vuln_payload.get("severity", []):
        if severity_entry.get("type", "").startswith("CVSS"):
            vector = severity_entry.get("score")
            score = _cvss_vector_to_score(vector)
            if score is not None:
                return score, vector
    # Some OSV records embed a numeric score directly under database_specific
    db_specific = vuln_payload.get("database_specific", {})
    numeric = db_specific.get("cvss_score") or db_specific.get("severity")
    if isinstance(numeric, (int, float)):
        return float(numeric), None
    return None, None


def _cvss_vector_to_score(vector: Optional[str]) -> Optional[float]:
    """
    Extremely small CVSS v3 base-score estimator used only when OSV
    supplies a vector string without a precomputed score. For production
    use, swap in a proper CVSS library (e.g. `cvss` on PyPI).
    """
    if not vector:
        return None
    # Placeholder heuristic: presence of AV:N (network) + PR:N (no privileges)
    # implies a higher severity band; this keeps the pipeline functional
    # even without the `cvss` dependency, but should be replaced with a
    # spec-accurate calculator before production use (see README).
    score = 5.0
    if "AV:N" in vector:
        score += 1.5
    if "PR:N" in vector:
        score += 1.0
    if "C:H" in vector or "I:H" in vector or "A:H" in vector:
        score += 1.5
    return min(round(score, 1), 10.0)


def _fixed_version_for(vuln_payload: dict[str, Any], ecosystem: str) -> Optional[str]:
    """Extract the earliest 'fixed' version event for the relevant ecosystem, if any."""
    for affected in vuln_payload.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("ecosystem") != ecosystem:
            continue
        for rng in affected.get("ranges", []):
            for event in rng.get("events", []):
                if "fixed" in event:
                    return event["fixed"]
    return None


class RiskAnalysisEngine:
    """
    Orchestrates OSV lookups + scoring for an application's full package set.
    Stateless aside from the DB session and OSV client it is given.
    """

    def __init__(self, db: Session, osv_client: Optional[OSVClient] = None) -> None:
        self.db = db
        self.osv_client = osv_client or OSVClient()

    async def scan_application(
        self, application_id: str, packages: list[ResolvedPackage]
    ) -> ScanResult:
        """
        Full pipeline: for every package, fetch OSV vulnerabilities, persist
        them, compute the risk profile, and persist that too.
        """
        start = time.perf_counter()
        vuln_count = 0
        profile_count = 0

        for pkg in packages:
            osv_vulns = await self.osv_client.query_package(
                package_name=pkg.name, ecosystem=pkg.ecosystem, version=pkg.version
            )
            persisted_links = self._persist_vulnerabilities(pkg, osv_vulns)
            vuln_count += len(persisted_links)

            profile = self._build_risk_profile(pkg, application_id, persisted_links)
            self.db.add(profile)
            profile_count += 1

        self.db.commit()
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ScanResult(
            application_id=application_id,
            packages_scanned=len(packages),
            vulnerabilities_found=vuln_count,
            profiles_generated=profile_count,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _persist_vulnerabilities(
        self, pkg: ResolvedPackage, osv_vulns: list[dict[str, Any]]
    ) -> list[models.PackageVulnerability]:
        links: list[models.PackageVulnerability] = []

        for raw in osv_vulns:
            vuln_id = raw.get("id")
            if not vuln_id:
                continue

            existing = (
                self.db.query(models.Vulnerability)
                .filter_by(vuln_id=vuln_id, source="OSV")
                .one_or_none()
            )
            cvss_score, cvss_vector = _extract_cvss(raw)

            if existing is None:
                existing = models.Vulnerability(
                    vuln_id=vuln_id,
                    source="OSV",
                    summary=raw.get("summary") or raw.get("details", "")[:500],
                    cvss_score=cvss_score,
                    cvss_vector=cvss_vector,
                    severity=_severity_from_cvss(cvss_score),
                    published_at=raw.get("published"),
                    raw_payload=raw,
                )
                self.db.add(existing)
                self.db.flush()  # assign PK before referencing it below

            fixed_version = _fixed_version_for(raw, pkg.ecosystem)
            link = models.PackageVulnerability(
                package_id=pkg.package_id,
                vulnerability_id=existing.id,
                affected_version=pkg.version,
                fixed_version=fixed_version,
                is_patch_available=fixed_version is not None,
                versions_behind_fix=(
                    _versions_behind(pkg.version, fixed_version) if fixed_version else None
                ),
            )
            link.vulnerability = existing
            links.append(link)

        return links

    def _build_risk_profile(
        self,
        pkg: ResolvedPackage,
        application_id: str,
        links: list[models.PackageVulnerability],
    ) -> models.PackageRiskProfile:
        # --- vulnerability score: worst-case CVSS across all known CVEs ---
        worst_link = None
        vuln_score = 0.0
        all_vulns_explained: list[dict[str, Any]] = []

        for link in links:
            v = link.vulnerability
            score = float(v.cvss_score) if v.cvss_score is not None else 0.0
            all_vulns_explained.append(
                {
                    "vuln_id": v.vuln_id,
                    "cvss_score": score,
                    "severity": v.severity,
                    "fixed_version": link.fixed_version,
                }
            )
            if score >= vuln_score:
                vuln_score = score
                worst_link = link

        # --- patch gap score: worst case across all known CVEs ---
        patch_gap = 0.0
        patch_reason = "No known vulnerabilities affecting this package."
        if links:
            gaps = []
            for link in links:
                if not link.is_patch_available:
                    gaps.append(10.0)
                elif link.versions_behind_fix in (None, 0):
                    gaps.append(0.0)
                else:
                    gaps.append(min(10.0, 2.0 * link.versions_behind_fix))
            patch_gap = max(gaps) if gaps else 0.0
            unpatched = [l.vulnerability.vuln_id for l in links if not l.is_patch_available]
            if unpatched:
                patch_reason = f"No fix published yet for: {', '.join(unpatched)}."
            elif worst_link is not None:
                patch_reason = (
                    f"Fix available in {worst_link.fixed_version}; "
                    f"currently {worst_link.versions_behind_fix or 0} release(s) behind."
                )

        # --- license score ---
        lic_score, lic_status, lic_reason = license_risk_score(pkg.license_id)

        explanation = {
            "worst_vulnerability": (
                {
                    "vuln_id": worst_link.vulnerability.vuln_id,
                    "cvss_score": float(worst_link.vulnerability.cvss_score or 0),
                    "severity": worst_link.vulnerability.severity,
                }
                if worst_link
                else None
            ),
            "all_vulnerabilities": all_vulns_explained,
            "patch_reasoning": patch_reason,
            "license_reasoning": lic_reason,
        }

        return models.PackageRiskProfile(
            package_id=pkg.package_id,
            application_id=application_id,
            vulnerability_score=round(vuln_score, 2),
            patch_gap_score=round(patch_gap, 2),
            license_risk_score=round(lic_score, 2),
            license_id=pkg.license_id,
            license_policy_status=lic_status.value,
            explanation=explanation,
            computed_at=datetime.utcnow(),
        )

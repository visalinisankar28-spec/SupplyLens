"""
EnterpriseDependencyIntelligenceEngine — core algorithms for Module 5.

Combines:
  - concentration/blast radius (this module, from resolved app membership)
  - dependency centrality (this module, via graph_service.py's NetworkX graph)
  - vulnerability + license components (Module 3, worst-case across apps)
  - repo health component (Module 4)
  - business criticality (governance input, this module)

into one explainable Enterprise Risk Score per package.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.enterprise_intelligence import graph_service, models
from app.modules.enterprise_intelligence.schemas import RecomputeResult

logger = logging.getLogger(__name__)

# Named weights for the final composite. Must sum to 1.0.
ENTERPRISE_WEIGHTS = {
    "vulnerability": 0.30,
    "repo_health": 0.20,
    "license": 0.15,
    "centrality": 0.20,
    "business_crit": 0.15,
}

CRITICALITY_WEIGHT = {
    "LOW": 2.5,
    "MEDIUM": 5.0,
    "HIGH": 7.5,
    "CRITICAL": 10.0,
}
DEFAULT_CRITICALITY = "MEDIUM"


class EnterpriseDependencyIntelligenceEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def recompute(self) -> RecomputeResult:
        """
        Full org-wide recompute: rebuild the dependency graph, recompute
        centrality, concentration, blast radius, and the final Enterprise
        Risk Score for every package. This is intentionally a full rebuild
        rather than incremental (see README, Future Improvements).
        """
        start = time.perf_counter()

        graph = graph_service.load_org_graph(self.db)
        betweenness = graph_service.compute_betweenness_centrality(graph)
        centrality_percentiles = graph_service.percentile_ranks(betweenness)
        membership = graph_service.application_membership(self.db)
        total_apps = graph_service.total_application_count(self.db)
        criticality_by_app = self._load_business_criticality()

        vuln_by_package = self._load_worst_case_vulnerability_components()
        license_by_package = self._load_worst_case_license_components()
        repo_health_by_package = self._load_repo_health_components()

        packages_analyzed = 0
        for package_id in graph.nodes:
            profile = self._build_profile(
                package_id=package_id,
                total_apps=total_apps,
                membership=membership,
                betweenness=betweenness,
                centrality_percentiles=centrality_percentiles,
                criticality_by_app=criticality_by_app,
                vuln_by_package=vuln_by_package,
                license_by_package=license_by_package,
                repo_health_by_package=repo_health_by_package,
            )
            self._upsert_profile(package_id, profile)
            packages_analyzed += 1

        self.db.commit()
        duration_ms = int((time.perf_counter() - start) * 1000)

        return RecomputeResult(
            packages_analyzed=packages_analyzed,
            total_applications=total_apps,
            graph_nodes=graph.number_of_nodes(),
            graph_edges=graph.number_of_edges(),
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------ #
    # Data loaders — pull the components this module composes, without
    # duplicating Module 3/4's own scoring logic.
    # ------------------------------------------------------------------ #

    def _load_business_criticality(self) -> dict[str, str]:
        rows = self.db.execute(
            text("SELECT application_id, criticality_level FROM application_business_criticality")
        ).fetchall()
        return {str(r.application_id): r.criticality_level for r in rows}

    def _load_worst_case_vulnerability_components(self) -> dict[str, float]:
        """Worst-case vulnerability_score across all of Module 3's per-application profiles."""
        rows = self.db.execute(
            text(
                """
                SELECT package_id, MAX(vulnerability_score) AS worst
                FROM package_risk_profiles
                GROUP BY package_id
                """
            )
        ).fetchall()
        return {str(r.package_id): float(r.worst) for r in rows}

    def _load_worst_case_license_components(self) -> dict[str, float]:
        rows = self.db.execute(
            text(
                """
                SELECT package_id, MAX(license_risk_score) AS worst
                FROM package_risk_profiles
                GROUP BY package_id
                """
            )
        ).fetchall()
        return {str(r.package_id): float(r.worst) for r in rows}

    def _load_repo_health_components(self) -> dict[str, float]:
        rows = self.db.execute(
            text("SELECT package_id, repo_health_score FROM repository_profiles")
        ).fetchall()
        return {str(r.package_id): float(r.repo_health_score) for r in rows}

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #

    def _build_profile(
        self,
        package_id: str,
        total_apps: int,
        membership: dict[str, set[str]],
        betweenness: dict[str, float],
        centrality_percentiles: dict[str, float],
        criticality_by_app: dict[str, str],
        vuln_by_package: dict[str, float],
        license_by_package: dict[str, float],
        repo_health_by_package: dict[str, float],
    ) -> dict[str, Any]:
        affected_apps = membership.get(package_id, set())
        application_count = len(affected_apps)
        concentration_ratio = (application_count / total_apps) if total_apps else 0.0

        betweenness_norm = centrality_percentiles.get(package_id, 0.0)
        concentration_component = round(concentration_ratio * 10, 2)
        centrality_score = round(0.5 * betweenness_norm + 0.5 * concentration_component, 2)

        criticality_score, criticality_reason = self._business_criticality_score(
            affected_apps, criticality_by_app
        )

        vuln_component = vuln_by_package.get(package_id, 0.0)
        license_component = license_by_package.get(package_id, 0.0)
        repo_health_component = repo_health_by_package.get(package_id, 5.0)  # neutral default if unscanned

        enterprise_risk_score = round(
            ENTERPRISE_WEIGHTS["vulnerability"] * vuln_component
            + ENTERPRISE_WEIGHTS["repo_health"] * repo_health_component
            + ENTERPRISE_WEIGHTS["license"] * license_component
            + ENTERPRISE_WEIGHTS["centrality"] * centrality_score
            + ENTERPRISE_WEIGHTS["business_crit"] * criticality_score,
            2,
        )

        explanation = {
            "concentration_reasoning": (
                f"Used by {application_count} of {total_apps} applications "
                f"({concentration_ratio * 100:.1f}% concentration)."
            ),
            "centrality_reasoning": (
                f"Betweenness percentile {betweenness_norm:.1f}/10, "
                f"concentration component {concentration_component:.1f}/10 -> "
                f"centrality score {centrality_score:.1f}/10."
            ),
            "business_criticality_reasoning": criticality_reason,
            "vulnerability_component": vuln_component,
            "license_component": license_component,
            "repo_health_component": repo_health_component,
            "weights": ENTERPRISE_WEIGHTS,
        }

        return dict(
            package_id=package_id,
            application_count=application_count,
            total_applications=total_apps,
            concentration_ratio=round(concentration_ratio, 4),
            betweenness_centrality=betweenness.get(package_id),
            centrality_score=centrality_score,
            blast_radius_app_count=application_count,
            affected_application_ids=sorted(affected_apps),
            business_criticality_score=criticality_score,
            vulnerability_component=vuln_component,
            repo_health_component=repo_health_component,
            license_component=license_component,
            enterprise_risk_score=enterprise_risk_score,
            explanation=explanation,
            computed_at=datetime.utcnow(),
        )

    @staticmethod
    def _business_criticality_score(
        affected_apps: set[str], criticality_by_app: dict[str, str]
    ) -> tuple[float, str]:
        if not affected_apps:
            return 0.0, "Not used by any application; no business criticality exposure."

        worst_level = "LOW"
        worst_score = -1.0
        for app_id in affected_apps:
            level = criticality_by_app.get(app_id, DEFAULT_CRITICALITY)
            score = CRITICALITY_WEIGHT.get(level, CRITICALITY_WEIGHT[DEFAULT_CRITICALITY])
            if score > worst_score:
                worst_score = score
                worst_level = level

        return worst_score, (
            f"Worst-case business criticality among {len(affected_apps)} affected "
            f"application(s): {worst_level}."
        )

    def _upsert_profile(self, package_id: str, profile: dict[str, Any]) -> None:
        existing = (
            self.db.query(models.EnterpriseDependencyProfile)
            .filter_by(package_id=package_id)
            .one_or_none()
        )
        if existing:
            for key, value in profile.items():
                setattr(existing, key, value)
        else:
            self.db.add(models.EnterpriseDependencyProfile(**profile))

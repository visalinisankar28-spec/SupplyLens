"""
Tests for Module 5 — Enterprise Dependency Intelligence Engine.

Run with: pytest backend/tests/test_enterprise_intelligence.py -v
"""
from __future__ import annotations

import networkx as nx
import pytest

from app.modules.enterprise_intelligence.graph_service import (
    compute_betweenness_centrality,
    percentile_ranks,
)
from app.modules.enterprise_intelligence.service import (
    CRITICALITY_WEIGHT,
    EnterpriseDependencyIntelligenceEngine,
)


# --------------------------------------------------------------------- #
# Graph centrality
# --------------------------------------------------------------------- #

def _bridge_fixture_graph() -> nx.DiGraph:
    """
    Three small clusters (a1-a2, b1-b2, c1-c2) all routed through a single
    'bridge' package. Bridge should have the highest betweenness centrality.
    """
    g = nx.DiGraph()
    edges = [
        ("app-a", "a1"), ("a1", "bridge"),
        ("app-b", "b1"), ("b1", "bridge"),
        ("app-c", "c1"), ("c1", "bridge"),
        ("bridge", "leaf1"), ("bridge", "leaf2"),
    ]
    g.add_edges_from(edges)
    return g


def test_bridge_package_has_highest_betweenness():
    g = _bridge_fixture_graph()
    centrality = compute_betweenness_centrality(g)
    bridge_score = centrality["bridge"]
    other_scores = [v for k, v in centrality.items() if k != "bridge"]
    assert all(bridge_score >= s for s in other_scores)
    assert bridge_score > 0


def test_percentile_ranks_bounds_and_ordering():
    raw = {"low": 0.01, "mid": 0.5, "high": 0.9}
    ranks = percentile_ranks(raw)
    assert ranks["low"] < ranks["mid"] < ranks["high"]
    assert min(ranks.values()) == 0.0
    assert max(ranks.values()) == 10.0


def test_percentile_ranks_empty_graph():
    assert percentile_ranks({}) == {}


def test_percentile_ranks_single_node():
    assert percentile_ranks({"only": 0.5}) == {"only": 0.0}


# --------------------------------------------------------------------- #
# Business criticality aggregation (worst-case, not average)
# --------------------------------------------------------------------- #

def test_business_criticality_worst_case_wins():
    affected_apps = {"app-low", "app-critical", "app-medium"}
    criticality_by_app = {
        "app-low": "LOW",
        "app-critical": "CRITICAL",
        "app-medium": "MEDIUM",
    }
    score, reason = EnterpriseDependencyIntelligenceEngine._business_criticality_score(
        affected_apps, criticality_by_app
    )
    assert score == CRITICALITY_WEIGHT["CRITICAL"]
    assert "CRITICAL" in reason


def test_business_criticality_no_apps_means_zero_exposure():
    score, reason = EnterpriseDependencyIntelligenceEngine._business_criticality_score(set(), {})
    assert score == 0.0
    assert "not used" in reason.lower()


def test_business_criticality_missing_tag_defaults_to_medium():
    affected_apps = {"app-untagged"}
    score, _ = EnterpriseDependencyIntelligenceEngine._business_criticality_score(
        affected_apps, criticality_by_app={}
    )
    assert score == CRITICALITY_WEIGHT["MEDIUM"]


# --------------------------------------------------------------------- #
# Composite weighting sums to 1.0 (guards against silent drift when
# someone tweaks a weight without updating the others)
# --------------------------------------------------------------------- #

def test_enterprise_weights_sum_to_one():
    from app.modules.enterprise_intelligence.service import ENTERPRISE_WEIGHTS

    assert abs(sum(ENTERPRISE_WEIGHTS.values()) - 1.0) < 1e-9

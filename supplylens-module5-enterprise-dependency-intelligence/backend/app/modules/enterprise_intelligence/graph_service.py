"""
Builds the single organization-wide dependency graph that is the whole
point of the Enterprise Dependency Intelligence Engine — instead of one
graph per application (Module 2's job), this constructs one graph spanning
every application's resolved dependencies, with package identity already
deduplicated (same package_id = same node, regardless of which app(s)
reference it).

Assumes Module 2 exposes a global, deduplicated edge list:
    dependency_edges(parent_package_id, child_package_id)
meaning "parent_package_id depends on child_package_id". If your Module 2
schema scopes edges per-application instead, adjust `load_org_graph`'s
query to UNION across applications and dedupe edges before building the
graph — the algorithms below are agnostic to how the edges were sourced.
"""
from __future__ import annotations

import logging
from typing import Iterable

import networkx as nx
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def load_org_graph(db: Session) -> nx.DiGraph:
    """
    Constructs a directed graph: edge (A -> B) means package A depends on
    package B. Nodes are package_id strings.
    """
    graph = nx.DiGraph()

    package_rows = db.execute(text("SELECT id FROM packages")).fetchall()
    graph.add_nodes_from(str(r.id) for r in package_rows)

    edge_rows = db.execute(
        text("SELECT parent_package_id, child_package_id FROM dependency_edges")
    ).fetchall()
    graph.add_edges_from(
        (str(r.parent_package_id), str(r.child_package_id)) for r in edge_rows
    )

    logger.info("Loaded org dependency graph: %d nodes, %d edges", graph.number_of_nodes(), graph.number_of_edges())
    return graph


def compute_betweenness_centrality(graph: nx.DiGraph) -> dict[str, float]:
    """
    Standard NetworkX betweenness centrality. For large graphs this is the
    most expensive step in the pipeline (O(V*E)); if the org graph grows
    beyond a few thousand packages, switch to `k`-sampled approximation
    (`k=` parameter) — flagged in README's Future Improvements.
    """
    if graph.number_of_nodes() == 0:
        return {}
    return nx.betweenness_centrality(graph, normalized=True)


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """
    Converts raw centrality values into a 0-10 percentile-rank scale, so a
    package's centrality score is relative to the rest of the current org
    graph rather than an arbitrary absolute unit. Returns 0.0 for all nodes
    if the graph is empty or all values are identical (no differentiation
    possible).
    """
    if not values:
        return {}

    sorted_ids = sorted(values, key=lambda k: values[k])
    n = len(sorted_ids)
    if n == 1:
        return {sorted_ids[0]: 0.0}

    ranks: dict[str, float] = {}
    for index, node_id in enumerate(sorted_ids):
        percentile = index / (n - 1)  # 0.0 (lowest) .. 1.0 (highest)
        ranks[node_id] = round(percentile * 10, 4)
    return ranks


def application_membership(db: Session) -> dict[str, set[str]]:
    """Returns {package_id: {application_id, ...}} from the resolved membership table."""
    rows = db.execute(
        text("SELECT package_id, application_id FROM application_packages")
    ).fetchall()

    membership: dict[str, set[str]] = {}
    for r in rows:
        membership.setdefault(str(r.package_id), set()).add(str(r.application_id))
    return membership


def total_application_count(db: Session) -> int:
    return db.execute(text("SELECT COUNT(*) AS c FROM applications")).scalar_one()

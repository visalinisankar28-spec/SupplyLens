# Module 5 — Enterprise Dependency Intelligence Engine

## 1. Purpose

This is SupplyLens's core differentiator. Modules 3 and 4 score a package
*within the context of one application*. This module steps back and asks
the question no per-app SCA tool can answer: **"across our entire
application portfolio, which dependencies, if compromised, would take down
the most systems at once?"**

It does this by:

1. Building a single **organization-wide dependency graph** (NetworkX)
   spanning every application, instead of analyzing each app in isolation.
2. Computing **dependency concentration** — how many applications share a
   given package.
3. Computing **organizational blast radius** — the concrete set/count of
   applications exposed if a given package turns out to be malicious or
   critically vulnerable.
4. Computing **dependency centrality** (graph betweenness) to surface
   **critical dependency clusters** — structurally important packages that
   quietly bridge large parts of the dependency graph together, i.e.
   single points of failure at the *organization* level, not just the repo
   level (that was Module 4's bus-factor, which is repo-maintainer
   concentration; this is graph-structure concentration).
5. Folding all of the above together with Module 3's vulnerability/license
   scores, Module 4's repository health score, and a governance-supplied
   **business criticality** rating per application, into one final,
   fully explainable **Enterprise Risk Score** per package.

No black-box model is used anywhere in this pipeline — every number is a
named, auditable formula over concrete inputs, consistent with Modules 3
and 4.

## 2. Folder Structure

```
backend/
└── app/
    └── modules/
        └── enterprise_intelligence/
            ├── __init__.py
            ├── models.py               # SQLAlchemy ORM models
            ├── schemas.py               # Pydantic schemas
            ├── graph_service.py         # builds the org-wide NetworkX graph
            ├── service.py               # EnterpriseDependencyIntelligenceEngine
            ├── router.py                # FastAPI routes
            └── README_MODULE5.md
└── tests/
    └── test_enterprise_intelligence.py
frontend/
└── src/
    └── components/
        └── EnterpriseIntelligence/
            ├── EnterpriseRiskScoreCard.jsx
            ├── BlastRadiusGraph.jsx        # Cytoscape.js
            └── SharedDependencyConcentration.jsx
```

## 3. Database Schema

```sql
-- Governance input: how critical is each application to the business.
-- Feeds the business_criticality_component of the Enterprise Risk Score.
CREATE TABLE application_business_criticality (
    application_id      UUID PRIMARY KEY REFERENCES applications(id) ON DELETE CASCADE,
    criticality_level   VARCHAR(16) NOT NULL DEFAULT 'MEDIUM',  -- LOW/MEDIUM/HIGH/CRITICAL
    updated_at           TIMESTAMP NOT NULL DEFAULT now()
);

-- One row per package, computed ORG-WIDE (not per application).
-- This is the table the Governance Dashboard (Module 6) reads from.
CREATE TABLE enterprise_dependency_profiles (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id                   UUID NOT NULL UNIQUE REFERENCES packages(id) ON DELETE CASCADE,

    application_count            INTEGER NOT NULL,       -- how many apps use this package
    total_applications            INTEGER NOT NULL,       -- org's total app count at compute time
    concentration_ratio           NUMERIC(5,4) NOT NULL,   -- application_count / total_applications

    betweenness_centrality        NUMERIC(8,6),             -- raw NetworkX betweenness centrality
    centrality_score              NUMERIC(4,2) NOT NULL,   -- 0-10, normalized composite (see 5.3)

    blast_radius_app_count        INTEGER NOT NULL,        -- apps exposed if this package is compromised
    affected_application_ids      JSONB NOT NULL,           -- concrete list, drives the blast-radius graph UI

    business_criticality_score    NUMERIC(4,2) NOT NULL,    -- worst-case criticality among affected apps

    vulnerability_component       NUMERIC(4,2) NOT NULL,    -- sourced from Module 3
    repo_health_component         NUMERIC(4,2) NOT NULL,    -- sourced from Module 4
    license_component             NUMERIC(4,2) NOT NULL,    -- sourced from Module 3

    enterprise_risk_score          NUMERIC(4,2) NOT NULL,
    explanation                    JSONB NOT NULL,
    computed_at                     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_enterprise_profile_score ON enterprise_dependency_profiles(enterprise_risk_score DESC);
CREATE INDEX idx_enterprise_profile_concentration ON enterprise_dependency_profiles(concentration_ratio DESC);
```

`packages`, `applications`, and `application_packages` (already-resolved,
direct + transitive package membership per app) are assumed to be owned by
Modules 1/2, per the same convention as Modules 3 and 4.

## 4. API Endpoints

Mounted under `/api/v1/enterprise-intelligence`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/recompute` | Rebuilds the org-wide dependency graph and recomputes every package's `enterprise_dependency_profiles` row. This is an org-wide operation, not scoped to one application. |
| `GET` | `/shared-dependencies?min_apps=2` | Packages used by at least `min_apps` applications, sorted by `concentration_ratio` desc. |
| `GET` | `/blast-radius/{package_id}` | Concrete list of applications exposed if this package is compromised, plus the graph path used to justify it. |
| `GET` | `/critical-clusters?top=10` | Top-N packages by combined centrality × concentration — the "single points of failure" of the whole dependency graph. |
| `GET` | `/enterprise-risk-scores?top=20` | Top-N riskiest packages org-wide, fully explained. |
| `PUT` | `/applications/{application_id}/business-criticality` | Governance input: set an application's business criticality (LOW/MEDIUM/HIGH/CRITICAL). |

## 5. Algorithms

### 5.1 Dependency Concentration

```
concentration_ratio(P) = application_count(P) / total_applications
```

`application_count(P)` counts distinct applications where P appears in
`application_packages` — which Module 2 already resolves to include
*transitive* dependencies, so this is concentration across the full
dependency tree, not just direct requirements.

### 5.2 Organizational Blast Radius

```
blast_radius_app_count(P) = application_count(P)     # same underlying set
affected_application_ids(P) = { app_id : P ∈ resolved_packages(app_id) }
```

Framed as a distinct concept from concentration for governance
communication ("12 of our 40 applications would be affected if this
package were compromised today") even though it is computed from the same
underlying resolved-membership data — deliberately, so it doesn't require
re-deriving reachability that Module 2 already solved.

### 5.3 Dependency Centrality Score

Two independent signals, averaged:

```
betweenness_norm(P) = percentile_rank(betweenness_centrality(P) across all packages)  # 0-10
concentration_component(P) = concentration_ratio(P) * 10                                # 0-10

centrality_score(P) = 0.5 * betweenness_norm(P) + 0.5 * concentration_component(P)
```

`betweenness_centrality` is standard NetworkX graph betweenness over the
org-wide dependency graph (nodes = packages, edges = "depends on",
deduplicated across all applications) — it captures packages that
structurally bridge otherwise-unconnected parts of the dependency graph,
which concentration alone would miss (a package could be used by many apps
but sit at a graph "leaf", vs. a package used by fewer apps but that
everything routes through).

### 5.4 Business Criticality Component

```
CRITICALITY_WEIGHT = {LOW: 2.5, MEDIUM: 5.0, HIGH: 7.5, CRITICAL: 10.0}

business_criticality_score(P) = max(
    CRITICALITY_WEIGHT[criticality_level(app)]
    for app in affected_applications(P)
)
```

Worst-case, not average — if even one CRITICAL-tagged application depends
on P, that risk should not be diluted by nine LOW-tagged ones.

### 5.5 Enterprise Risk Score (final composite)

```
ENTERPRISE_WEIGHTS = {
    "vulnerability": 0.30,
    "repo_health":   0.20,
    "license":       0.15,
    "centrality":    0.20,
    "business_crit": 0.15,
}

enterprise_risk_score(P) =
      0.30 * vulnerability_component(P)      # worst-case from Module 3, across all apps using P
    + 0.20 * repo_health_component(P)         # from Module 4
    + 0.15 * license_component(P)             # from Module 3
    + 0.20 * centrality_score(P)              # from 5.3 above
    + 0.15 * business_criticality_score(P)    # from 5.4 above
```

`vulnerability_component` and `license_component` are pulled as the
worst-case value across every `PackageRiskProfile` row for that package_id
(Module 3 already computes these per-application; since the same package_id
is shared, we take the max — one CVE affecting the package is a real risk
regardless of which application surfaced it first).

Every term above is stored, per package, in `explanation` — a reviewer can
trace the final number back to: which CVE drove the vulnerability
component, which applications drove blast radius/business criticality, and
what the raw betweenness centrality was.

## 6. Python Implementation

See `graph_service.py` (org-wide graph construction + centrality),
`service.py` (`EnterpriseDependencyIntelligenceEngine` — concentration,
blast radius, composite scoring), `models.py`, `schemas.py`, `router.py`.

## 7. Frontend Implementation

See `frontend/src/components/EnterpriseIntelligence/`:
- `EnterpriseRiskScoreCard.jsx` — final score + full component breakdown.
- `BlastRadiusGraph.jsx` — Cytoscape.js graph, package node in the center,
  affected applications radiating outward, for the "if this breaks, here's
  what goes down" visual that's the whole point of this module.
- `SharedDependencyConcentration.jsx` — Recharts bar chart of top shared
  dependencies by application count.

## 8. Testing Strategy

- **Unit tests**: concentration ratio math, business-criticality max-based
  aggregation, composite weighting arithmetic, betweenness normalization
  (percentile-rank correctness on a small fixture graph).
- **Graph tests**: build a small fixture org graph (3 apps, some shared
  packages, one clear bridge package) and assert `graph_service.py`
  correctly identifies the bridge package as highest centrality.
- **Integration test**: end-to-end `recompute()` against a fixture DB with
  known Module 3/4 outputs already seeded, asserting the final
  `enterprise_risk_score` matches a hand-calculated expected value.

## 9. Future Improvements

- Weighted blast radius: instead of a flat app count, weight by each
  affected application's user base / revenue exposure, not just its
  criticality tag.
- Temporal risk propagation: model how long it would take a critical CVE
  in a highly-central package to actually reach production in each
  affected application (deployment cadence-aware).
- Cluster detection (e.g. Louvain community detection) to group packages
  into "dependency neighborhoods" for the Governance Dashboard, beyond
  single-package centrality.
- Incremental recomputation: recompute only the affected subgraph when a
  single application's SBOM changes, instead of a full org-wide rebuild.

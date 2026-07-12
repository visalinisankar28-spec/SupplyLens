# Module 3 — Risk Analysis Engine

## 1. Purpose

The Risk Analysis Engine is the module that turns raw dependency data (produced by
Module 1 — SBOM Parser, and Module 2 — Dependency Graph Engine) into a
**per-package, explainable risk profile**.

It answers three questions for every package version in the graph:

1. **Is it vulnerable?** — known CVEs / GHSA advisories, mapped to CVSS severity.
2. **Is it patchable?** — is there a fixed version available, and how far behind is
   the app from that fixed version.
3. **Is it legally safe to use?** — does its license conflict with the
   organization's declared license policy, or with the licenses of other
   packages it is bundled with.

The output of this module (`PackageRiskProfile`) is **not** the final Enterprise
Risk Score — that aggregation happens in Module 5 (Enterprise Dependency
Intelligence Engine), which combines this module's output with repository
health signals from Module 4. This module owns *vulnerability + license* risk
only, and every number it produces is traceable back to a specific CVE ID,
CVSS vector, or license rule — no opaque ML scoring.

## 2. Folder Structure

```
backend/
└── app/
    ├── core/
    │   ├── config.py               # env-driven settings (already used by all modules)
    │   └── database.py             # SQLAlchemy engine/session (shared)
    └── modules/
        └── risk_analysis/
            ├── __init__.py
            ├── models.py            # SQLAlchemy ORM models
            ├── schemas.py           # Pydantic request/response schemas
            ├── osv_client.py        # OSV.dev API client (async)
            ├── license_compat.py    # License compatibility rule engine
            ├── service.py           # RiskAnalysisEngine - core algorithms
            ├── router.py            # FastAPI routes
            └── README_MODULE3.md
└── tests/
    └── test_risk_analysis.py
frontend/
└── src/
    └── components/
        └── RiskAnalysis/
            ├── RiskBadge.jsx
            ├── VulnerabilityTable.jsx
            └── PackageRiskPanel.jsx
```

## 3. Database Schema

Three tables, all keyed to `package_id` (FK to the `packages` table owned by
Module 1's SBOM Parser).

```sql
-- Raw vulnerability records pulled from OSV, cached locally
CREATE TABLE vulnerabilities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vuln_id             VARCHAR(64)  NOT NULL,      -- e.g. GHSA-xxxx or CVE-2023-xxxx
    source              VARCHAR(32)  NOT NULL,      -- 'OSV'
    summary             TEXT,
    cvss_score          NUMERIC(3,1),                -- 0.0 - 10.0
    cvss_vector         VARCHAR(128),
    severity            VARCHAR(16),                 -- LOW/MEDIUM/HIGH/CRITICAL
    published_at        TIMESTAMP,
    raw_payload         JSONB,                        -- full OSV response, for audit
    fetched_at          TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (vuln_id, source)
);

-- Which package versions are affected, and what fixes them
CREATE TABLE package_vulnerabilities (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id          UUID NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    vulnerability_id    UUID NOT NULL REFERENCES vulnerabilities(id) ON DELETE CASCADE,
    affected_version    VARCHAR(64) NOT NULL,
    fixed_version       VARCHAR(64),                  -- NULL if no fix published yet
    is_patch_available  BOOLEAN NOT NULL DEFAULT false,
    versions_behind_fix  INTEGER,                      -- computed distance to fix
    UNIQUE (package_id, vulnerability_id)
);

-- Explainable per-package risk snapshot (recomputed on each scan)
CREATE TABLE package_risk_profiles (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id            UUID NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    application_id        UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    vulnerability_score   NUMERIC(4,2) NOT NULL,   -- 0-10, worst-case CVSS weighted
    patch_gap_score       NUMERIC(4,2) NOT NULL,   -- 0-10, based on fix availability/staleness
    license_risk_score    NUMERIC(4,2) NOT NULL,   -- 0-10, from license_compat.py
    license_id            VARCHAR(64),
    license_policy_status VARCHAR(16),              -- ALLOWED / REVIEW / DENIED
    explanation           JSONB NOT NULL,            -- structured breakdown, see service.py
    computed_at           TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX idx_pkg_vuln_package ON package_vulnerabilities(package_id);
CREATE INDEX idx_risk_profile_app ON package_risk_profiles(application_id);
```

`packages` and `applications` are owned by Modules 1/2 — this module only adds
foreign keys onto them, it never duplicates their schema.

## 4. API Endpoints

All routes are mounted under `/api/v1/risk-analysis`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/scan/{application_id}` | Runs vulnerability + license analysis for every package in an application's dependency graph. Fetches from OSV, upserts `vulnerabilities` / `package_vulnerabilities`, recomputes `package_risk_profiles`. |
| `GET` | `/applications/{application_id}/profile` | Returns the full list of `PackageRiskProfile` for an application, sorted by `vulnerability_score` desc. |
| `GET` | `/packages/{package_id}/vulnerabilities` | Returns raw vulnerability records for a single package. |
| `GET` | `/applications/{application_id}/summary` | Aggregated counts (critical/high/medium/low, license violations, patchable vs unpatchable) — feeds Module 6 dashboards. |

## 5. Algorithms

### 5.1 Vulnerability Score (per package)

For a package with vulnerabilities `V = {v1, v2, ..., vn}`:

```
vulnerability_score = max(cvss(v) for v in V)   if V is non-empty
                     = 0.0                       otherwise
```

We use **max**, not average — one critical CVE should not be diluted by
several low-severity ones. The full list is kept in `explanation` so the UI
can show *why*.

### 5.2 Patch Gap Score

For each vulnerability affecting the package:

```
if no fixed_version published:
    patch_gap = 10.0        # worst case: unpatchable today
elif current_version == fixed_version already satisfied:
    patch_gap = 0.0
else:
    versions_behind = semantic_distance(current_version, fixed_version)
    patch_gap = min(10.0, 2.0 * versions_behind)   # capped, linear penalty
```

`patch_gap_score` for the package = max across its vulnerabilities (same
"worst case wins" reasoning as above).

### 5.3 License Risk Score

Handled by `license_compat.py`'s static compatibility matrix
(SPDX identifiers → risk tier), see below. Score bands:

| Policy status | Score |
|---|---|
| ALLOWED (e.g. MIT, Apache-2.0, BSD-3-Clause) | 0.0 |
| REVIEW (e.g. LGPL-2.1, MPL-2.0 — copyleft with linking exceptions) | 5.0 |
| DENIED (e.g. GPL-3.0, AGPL-3.0 in a proprietary product) | 10.0 |
| UNKNOWN (no SPDX identifier found) | 6.0 (treated conservatively) |

### 5.4 Why this stays explainable

Every score above is a deterministic function of: a CVSS number from OSV, a
semantic version diff, or a lookup in a static table. `explanation` (JSONB)
stores the exact vulnerability IDs, versions, and license rule that produced
each number, so the Governance Dashboard (Module 6) can always show "why is
this 8.6 and not 9.0" down to the CVE.

## 6. Python Implementation

See `models.py`, `schemas.py`, `osv_client.py`, `license_compat.py`,
`service.py`, `router.py` in this directory.

## 7. Frontend Implementation

See `frontend/src/components/RiskAnalysis/` — `RiskBadge.jsx` (colored
severity chip), `VulnerabilityTable.jsx` (Recharts + sortable table), and
`PackageRiskPanel.jsx` (per-package explainable breakdown, drawer style).

## 8. Testing Strategy

- **Unit tests** (`tests/test_risk_analysis.py`):
  - `license_compat.py` classification for a fixed set of SPDX IDs.
  - `patch_gap` calculation for version triples (behind by 0, 1, 3 majors, no fix).
  - `vulnerability_score` max-aggregation with 0/1/many CVEs.
- **Integration tests** (mocked OSV client):
  - `POST /scan/{application_id}` against a fixture SBOM with known CVEs,
    asserting rows land correctly in `package_vulnerabilities` and
    `package_risk_profiles`.
- **Contract test**: OSV client response schema is validated against a
  recorded fixture so upstream API changes fail loudly instead of silently
  under-scoring risk.

## 9. Future Improvements

- Add GHSA and NVD as secondary vulnerability sources with de-duplication
  against OSV IDs (aliases).
- EPSS (Exploit Prediction Scoring System) integration to weight
  `vulnerability_score` by real-world exploitation likelihood, not just CVSS.
- Configurable, per-organization license policy (currently a static matrix)
  stored in DB and editable from the Governance Dashboard.
- Reachability analysis (is the vulnerable function actually called?) to
  reduce false-positive risk — flagged as a stretch goal, not required for
  the hackathon scope.

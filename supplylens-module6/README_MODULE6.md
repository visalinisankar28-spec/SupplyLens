# Module 6 — Governance Reporting

Part of **SupplyLens — Enterprise Dependency Intelligence for Software Supply Chain Resilience**

This module sits on top of Modules 1–5 (SBOM Parser, Dependency Graph Engine,
Risk Analysis Engine, Repository Intelligence Engine, Enterprise Dependency
Intelligence Engine). It does not compute new risk primitives — it aggregates,
ranks, and presents what those engines already produced, and packages it into
artifacts a CISO / Governance, Risk & Compliance (GRC) team can act on.

---

## 1. Purpose

Governance Reporting is the layer executives and security leadership actually
look at. Engineers look at graphs; leadership looks at a one-page summary and
a ranked remediation list. This module provides:

- **Organization-wide risk summary** — single-screen health of the entire
  application portfolio (counts, score distribution, trend deltas).
- **Top Risky Applications** — applications ranked by their own Enterprise
  Risk Score contribution.
- **Top Risky Dependencies** — individual packages ranked by combined
  severity × blast radius × repo health.
- **Top Shared Dependencies** — packages used by the largest number of
  applications (concentration risk / single point of failure candidates).
- **Remediation Priority** — a single ranked worklist telling a security team
  exactly what to fix first, with an explainable justification per row.
- **Executive PDF Export** — a formatted, printable report for audits, board
  packs, or a Société Générale-style security review.

Everything here is a deterministic aggregation/ranking over existing
persisted data — **no black-box model**, every number in the report can be
traced back to a row in `enterprise_risk_scores`, `dependency_risk_scores`,
or `repository_health`.

---

## 2. Folder structure

```
backend/
└── app/
    └── modules/
        └── governance/
            ├── __init__.py
            ├── schemas.py          # Pydantic response/request models
            ├── service.py          # aggregation + ranking + PDF business logic
            ├── router.py           # FastAPI routes
            ├── pdf_report.py       # ReportLab executive PDF generator
            └── tests/
                ├── __init__.py
                ├── test_service.py
                └── test_router.py
frontend/
└── src/
    └── pages/
        └── GovernanceDashboard/
            ├── GovernanceDashboard.jsx
            ├── api/
            │   └── governanceApi.js
            └── components/
                ├── RiskSummaryCards.jsx
                ├── RiskDistributionChart.jsx
                ├── TopRiskyApplications.jsx
                ├── TopRiskyDependencies.jsx
                ├── TopSharedDependencies.jsx
                └── RemediationPriorityTable.jsx
migrations/
└── 0006_governance_reporting.sql
```

This folder tree is meant to be dropped straight into the existing
`supplylens/` monorepo produced by Modules 1–5 — paths match that layout.

---

## 3. Database schema

Governance Reporting is read-mostly. It reads from tables assumed to already
exist from earlier modules:

- `applications(id, name, business_criticality, owner_team)`
- `dependencies(id, name, ecosystem, latest_version)`
- `application_dependencies(application_id, dependency_id, version, is_direct)`
- `vulnerabilities(id, dependency_id, cve_id, cvss_score, patch_available)`
- `repository_health(dependency_id, scorecard_score, stars, contributors, last_release_at, is_maintained)`
- `dependency_risk_scores(dependency_id, vulnerability_score, license_risk_score, repo_health_score, centrality_score, final_score, explanation_json)`
- `enterprise_risk_scores(application_id, score, blast_radius, spof_count, computed_at, explanation_json)`
- `shared_dependencies(dependency_id, application_count, application_ids)`

It adds two of its own objects:

```sql
-- migrations/0006_governance_reporting.sql

-- 1. Persist every generated PDF export so it can be re-downloaded /
--    audited later instead of regenerated.
CREATE TABLE IF NOT EXISTS report_exports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_type     VARCHAR(50)  NOT NULL DEFAULT 'executive_summary',
    generated_by    VARCHAR(255) NOT NULL,
    file_path       TEXT         NOT NULL,
    filters_json    JSONB        NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_exports_created_at
    ON report_exports (created_at DESC);

-- 2. Materialized view used by /governance/remediation-priority so the
--    ranking query doesn't re-join five tables on every request.
CREATE MATERIALIZED VIEW IF NOT EXISTS remediation_priority_view AS
SELECT
    d.id                              AS dependency_id,
    d.name                            AS dependency_name,
    d.ecosystem                       AS ecosystem,
    drs.final_score                   AS risk_score,
    sd.application_count              AS affected_application_count,
    COALESCE(v.max_cvss, 0)           AS max_cvss,
    COALESCE(v.has_patch, false)      AS patch_available,
    rh.scorecard_score                AS repo_health_score,
    rh.is_maintained                  AS is_maintained
FROM dependencies d
JOIN dependency_risk_scores drs   ON drs.dependency_id = d.id
LEFT JOIN shared_dependencies sd  ON sd.dependency_id = d.id
LEFT JOIN repository_health rh    ON rh.dependency_id = d.id
LEFT JOIN (
    SELECT dependency_id,
           MAX(cvss_score) AS max_cvss,
           BOOL_OR(patch_available) AS has_patch
    FROM vulnerabilities
    GROUP BY dependency_id
) v ON v.dependency_id = d.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_remediation_priority_dependency
    ON remediation_priority_view (dependency_id);

-- Refresh on a schedule (e.g. after every SBOM ingest / nightly cron):
-- REFRESH MATERIALIZED VIEW CONCURRENTLY remediation_priority_view;
```

---

## 4. API endpoints

All routes are mounted under `/api/v1/governance`.

| Method | Path                                   | Description |
|--------|----------------------------------------|--------------|
| GET    | `/summary`                             | Portfolio-wide counts, average/median risk, score distribution buckets |
| GET    | `/top-risky-applications?limit=10`     | Applications ranked by Enterprise Risk Score |
| GET    | `/top-risky-dependencies?limit=10`     | Dependencies ranked by combined risk factors |
| GET    | `/top-shared-dependencies?limit=10`    | Dependencies ranked by number of consuming applications |
| GET    | `/remediation-priority?limit=25`       | Single ranked worklist with explanation per item |
| POST   | `/export/pdf`                          | Kick off generation of an executive PDF report, returns `report_id` |
| GET    | `/export/{report_id}/download`         | Stream the generated PDF back to the caller |
| GET    | `/export/history?limit=20`             | List previously generated reports (audit trail) |

---

## 5. Algorithms

### 5.1 Remediation Priority Score

The remediation list is the most important governance artifact — it has to
be explainable, so it's a weighted linear combination, not a model:

```
priority_score =
      0.35 * normalized(risk_score)
    + 0.30 * normalized(affected_application_count)   # blast radius proxy
    + 0.20 * normalized(max_cvss)
    + 0.15 * patch_penalty

patch_penalty = 0  if patch_available else 1   (scaled 0-1, weighted 0.15)
```

`normalized(x)` = min-max scaling against the current result set so scores
stay in a comparable 0–1 range regardless of absolute magnitudes. Every
dependency's row carries the four raw inputs plus the weights, so the UI
and PDF can render a one-line "why this is #1" explanation, e.g.:

> "Ranked #1: CVSS 9.8, no patch available, used by 14 of 20 applications."

### 5.2 Risk Distribution Buckets

For the summary chart, Enterprise Risk Scores (0–100) are bucketed into
`Low (0–39)`, `Medium (40–69)`, `High (70–89)`, `Critical (90–100)` — fixed,
documented thresholds rather than percentiles, so a "Critical" app in
January and a "Critical" app in June mean the same thing.

### 5.3 Top-N Ranking

Straightforward `ORDER BY <score> DESC LIMIT N` against the relevant table /
materialized view — deliberately simple and auditable, consistent with the
"no black-box" principle stated for the whole project.

---

## Files below are the actual implementation, ready to drop into your repo.

## 8. Testing strategy

**Backend**
- `tests/test_service.py` — unit tests for the pure/deterministic helpers
  (`_bucket_for`, `_normalize`) with no DB dependency. Also pins the
  remediation-priority weights (0.35 / 0.30 / 0.20 / 0.15) so a future edit
  can't silently drift them away from what README §5.1 documents.
- `tests/test_router.py` — FastAPI `TestClient` tests with the `get_db`
  dependency and `service.*` functions mocked, covering status codes,
  input validation (`limit` bounds), and response shape for every route.
- Recommended for CI (not included here to keep this module dependency-free
  of a test container): an integration suite against a throwaway Postgres
  instance (e.g. `testcontainers-python`) that seeds `applications`,
  `dependency_risk_scores`, etc. and asserts the SQL in `service.py`
  actually ranks correctly end-to-end, plus a snapshot test that opens the
  generated PDF and asserts page count / table row counts.

**Frontend**
- Component tests with React Testing Library: render each table component
  with a fixture array and assert row count + the "empty state" message
  when the array is empty.
- `GovernanceDashboard.jsx` integration test: mock `governanceApi` module,
  assert loading → loaded transition, and that clicking "Export executive
  PDF" calls `exportPdf` and opens the returned `download_url`.

Run the included suite with:

```bash
cd backend
pip install -r requirements-governance.txt
pytest app/modules/governance/tests -v
```

## 9. Future improvements

- Trend lines (risk score over time) once `enterprise_risk_scores` keeps
  history instead of latest-only, to show whether governance actions are
  actually reducing risk sprint over sprint.
- Scheduled reports (nightly/weekly) emailed or posted to Slack/Teams
  automatically instead of on-demand export only.
- Role-based report views — an app-owner sees only their applications;
  a CISO sees the full portfolio.
- Drill-down from a remediation item straight into the dependency graph
  view (Module 5) to see exactly which applications/paths are affected.
- SLA tracking — attach a "days open" clock to each remediation item and
  surface items that have blown past an internal remediation SLA.

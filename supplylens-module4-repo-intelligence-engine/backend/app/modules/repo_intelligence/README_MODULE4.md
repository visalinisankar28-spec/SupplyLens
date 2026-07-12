# Module 4 — Repository & Maintenance Intelligence Engine

## 1. Purpose

Module 3 answers "is this package vulnerable *right now*?". Module 4 answers
the forward-looking question: **"can we trust the people maintaining this
package to keep fixing things?"**

It profiles the upstream repository behind every package — using OpenSSF
Scorecard plus raw repository metadata — and turns that into an explainable
**Repository Health Score**. This score feeds Module 5's Enterprise Risk
Score alongside vulnerability, patch, and license risk from Module 3.

Concretely, it captures:

- **Maintenance signal** — how recently was there a release / commit.
- **Activity signal** — commit and release cadence over time.
- **Bus-factor / concentration signal** — how much of the project's history
  sits with a single contributor (a hidden single point of failure that
  Module 5's Enterprise Dependency Intelligence Engine cares about deeply).
- **OpenSSF Scorecard composite** — branch protection, code review practice,
  pinned dependencies, vulnerability tooling, and other supply-chain
  hygiene checks that OpenSSF already standardizes.

As with Module 3, everything here is a deterministic function of concrete
inputs (a Scorecard sub-check score, a days-since-last-commit count) —
no opaque model.

## 2. Folder Structure

```
backend/
└── app/
    └── modules/
        └── repo_intelligence/
            ├── __init__.py
            ├── models.py               # SQLAlchemy ORM models
            ├── schemas.py               # Pydantic schemas
            ├── scorecard_client.py      # OpenSSF Scorecard REST API client
            ├── repo_metadata_client.py  # GitHub REST API client (stars/forks/commits/releases)
            ├── service.py               # RepoIntelligenceEngine - scoring algorithms
            ├── router.py                # FastAPI routes
            └── README_MODULE4.md
└── tests/
    └── test_repo_intelligence.py
frontend/
└── src/
    └── components/
        └── RepoIntelligence/
            ├── RepoHealthCard.jsx
            ├── MaintenanceTimeline.jsx
            └── ContributorBusFactor.jsx
```

## 3. Database Schema

```sql
CREATE TABLE repository_profiles (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id              UUID NOT NULL REFERENCES packages(id) ON DELETE CASCADE,
    repo_url                TEXT NOT NULL,
    repo_platform           VARCHAR(32) NOT NULL DEFAULT 'github',

    stars                   INTEGER,
    forks                   INTEGER,
    open_issues             INTEGER,
    contributors_count      INTEGER,

    last_commit_at          TIMESTAMP,
    last_release_at         TIMESTAMP,
    release_count_last_year INTEGER,

    top_contributor_commit_share NUMERIC(5,2),   -- 0-100, % of commits by single top contributor

    scorecard_overall_score NUMERIC(3,1),          -- 0-10, OpenSSF Scorecard aggregate
    scorecard_checks        JSONB,                  -- raw per-check breakdown, for audit

    maintenance_score       NUMERIC(4,2) NOT NULL,  -- 0-10, derived (see algorithms)
    activity_score          NUMERIC(4,2) NOT NULL,  -- 0-10, derived
    bus_factor_score        NUMERIC(4,2) NOT NULL,  -- 0-10, derived (higher = worse concentration)
    repo_health_score        NUMERIC(4,2) NOT NULL,  -- 0-10, weighted composite

    explanation              JSONB NOT NULL,
    fetched_at                TIMESTAMP NOT NULL DEFAULT now(),

    UNIQUE (package_id)
);

CREATE INDEX idx_repo_profile_package ON repository_profiles(package_id);
```

## 4. API Endpoints

Mounted under `/api/v1/repo-intelligence`.

| Method | Path | Description |
|---|---|---|
| `POST` | `/scan/{application_id}` | Fetches Scorecard + repo metadata for every package's upstream repo in an application, computes and persists `repository_profiles`. |
| `GET` | `/packages/{package_id}/profile` | Returns the repository health profile for a single package. |
| `GET` | `/applications/{application_id}/profiles` | Returns repository profiles for every package in an application, sorted worst-first by `repo_health_score`. |
| `GET` | `/applications/{application_id}/single-points-of-failure` | Returns packages whose `bus_factor_score` exceeds a configurable threshold (default 7.0) — i.e. maintained almost entirely by one person. |

## 5. Algorithms

### 5.1 Maintenance Score (0 = healthy, 10 = abandoned)

```
days_since_release = today - last_release_at
days_since_commit   = today - last_commit_at
staleness_days      = min(days_since_release, days_since_commit)

maintenance_score =
    0.0                          if staleness_days <= 90
    2.5                          if staleness_days <= 180
    5.0                          if staleness_days <= 365
    7.5                          if staleness_days <= 730
    10.0                         if staleness_days > 730 (2+ years untouched)
```

A step function rather than a continuous curve, deliberately — it maps to
plain-language bands ("actively maintained", "aging", "stale",
"unmaintained") that a non-technical reviewer in a governance report can
understand without needing the formula.

### 5.2 Activity Score

```
activity_score = 10.0 - min(10.0, release_count_last_year * 1.5)
```

More releases in the last year → lower activity-risk score. Capped so a
package with 7+ releases/year is treated as maximally active (0 risk); a
package with zero releases in the last year scores the full 10.

### 5.3 Bus Factor Score (concentration risk)

```
bus_factor_score =
    0.0   if top_contributor_commit_share < 30%
    3.0   if 30% <= share < 50%
    6.0   if 50% <= share < 75%
    10.0  if share >= 75%    (essentially a single maintainer)
```

This is intentionally the same signal Module 5 uses at the *organization*
level (dependency concentration) but computed here at the *single-repo*
level — "is this specific project one resignation away from going dark".

### 5.4 Repository Health Score (composite)

```
repo_health_score =
      0.40 * (10 - scorecard_overall_score)   # Scorecard already 0(bad)-10(good); invert to risk
    + 0.25 * maintenance_score
    + 0.20 * bus_factor_score
    + 0.15 * activity_score
```

Weights are configurable constants in `service.py` (`SCORE_WEIGHTS`), not
hardcoded magic numbers buried in logic — a reviewer can see and challenge
them directly.

## 6. Python Implementation

See `models.py`, `schemas.py`, `scorecard_client.py`,
`repo_metadata_client.py`, `service.py`, `router.py`.

## 7. Frontend Implementation

See `frontend/src/components/RepoIntelligence/`:
- `RepoHealthCard.jsx` — compact scorecard-style summary per package.
- `MaintenanceTimeline.jsx` — Recharts timeline of releases/commits vs. today.
- `ContributorBusFactor.jsx` — donut chart of commit share, flags single points of failure.

## 8. Testing Strategy

- **Unit tests**: maintenance-score banding at each boundary (89/90/91 days
  etc.), activity-score capping, bus-factor banding, composite weighting.
- **Integration tests** (mocked Scorecard + GitHub clients): full
  `scan_application` flow against fixture repos with known stats, asserting
  correct `repository_profiles` rows.
- **Contract test**: Scorecard API response shape validated against a
  recorded fixture (OpenSSF's schema is versioned; a breaking change should
  fail the test suite, not silently zero out scores).

## 9. Future Improvements

- Weight Scorecard sub-checks individually (e.g. "Dangerous-Workflow" and
  "Vulnerabilities" checks weighted higher than "CI-Tests") instead of only
  using the single aggregate score.
- Org-level aggregation: multiple repos under one maintainer/org counted as
  correlated risk, not independent bus factors.
- Detect "hobbyist to corporate-backed" maintainer transitions as a
  positive signal (e.g. a library adopted by a foundation).
- Cache Scorecard/GitHub responses with a TTL and ETag-based conditional
  requests to reduce API quota usage on large SBOMs.

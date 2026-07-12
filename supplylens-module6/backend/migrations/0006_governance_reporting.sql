-- Module 6: Governance Reporting
-- Adds report export tracking + a materialized view backing the
-- remediation priority ranking endpoint. Assumes tables from
-- Modules 1-5 already exist (applications, dependencies,
-- application_dependencies, vulnerabilities, repository_health,
-- dependency_risk_scores, enterprise_risk_scores, shared_dependencies).

CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

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

-- Refresh strategy: call after every SBOM ingest, or on a nightly cron job.
-- REFRESH MATERIALIZED VIEW CONCURRENTLY remediation_priority_view;

/**
 * Types mirroring backend/app/schemas/health.py.
 * Keep these two files in sync manually, or generate this file from the
 * OpenAPI schema (see README "Future Improvements") once the API is stable.
 */

export type HealthCategory =
  | "Healthy"
  | "Stable"
  | "Needs Attention"
  | "High Maintenance Risk";

export interface HealthProfile {
  component_id: string;
  repo_url: string | null;
  repo_resolved: boolean;

  scorecard_overall_score: number | null;
  contributors_count: number | null;
  is_archived: boolean;
  days_since_last_release: number | null;
  days_since_last_commit: number | null;

  maintenance_activity_score: number;
  release_cadence_score: number;
  community_resilience_score: number;
  security_hygiene_score: number;

  dhi_score: number;
  dhi_category: HealthCategory;
  explanation: string[];
}

export interface SbomHealthSummary {
  sbom_id: string;
  total_components: number;
  analyzed_components: number;
  category_breakdown: Record<string, number>;
  average_dhi_score: number;
  profiles: HealthProfile[];
}

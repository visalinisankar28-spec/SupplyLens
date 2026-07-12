import type { SbomHealthSummary } from "../types/health";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/** Runs (or refreshes) health analysis for every component in an SBOM. */
export async function analyzeSbomHealth(
  sbomId: string,
  forceRefresh = false
): Promise<SbomHealthSummary> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health/sbom/${sbomId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ force_refresh: forceRefresh }),
  });
  if (!response.ok) {
    throw new Error(`Health analysis request failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

/** Fetches the already-computed health summary for an SBOM, without re-querying external APIs. */
export async function getSbomHealth(sbomId: string): Promise<SbomHealthSummary> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health/sbom/${sbomId}`);
  if (!response.ok) {
    throw new Error(`Fetching SBOM health failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

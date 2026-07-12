// Thin fetch wrapper around the /api/v1/governance endpoints.
// Keeping this separate from components makes it trivial to swap in
// react-query / SWR later without touching any UI code.

const BASE_URL = "/api/v1/governance";

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Governance API error (${response.status}): ${body}`);
  }
  return response.json();
}

export const governanceApi = {
  getSummary: () => request("/summary"),

  getTopRiskyApplications: (limit = 10) =>
    request(`/top-risky-applications?limit=${limit}`),

  getTopRiskyDependencies: (limit = 10) =>
    request(`/top-risky-dependencies?limit=${limit}`),

  getTopSharedDependencies: (limit = 10) =>
    request(`/top-shared-dependencies?limit=${limit}`),

  getRemediationPriority: (limit = 25) =>
    request(`/remediation-priority?limit=${limit}`),

  exportPdf: (payload) =>
    request("/export/pdf", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getReportHistory: (limit = 20) => request(`/export/history?limit=${limit}`),

  downloadUrl: (reportId) => `${BASE_URL}/export/${reportId}/download`,
};

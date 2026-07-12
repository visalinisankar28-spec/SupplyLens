// Thin API client — no state, no side effects beyond the network call itself.
// Components own their own loading/error state; this file just knows the wire format.

export interface SBOMUploadResponse {
  sbom_document_id: string;
  application_id: string;
  format: "cyclonedx" | "spdx";
  spec_version: string | null;
  component_count: number;
  direct_dependency_count: number;
  edge_count: number;
  warnings: string[];
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class SBOMUploadError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
    this.name = "SBOMUploadError";
  }
}

export async function uploadSBOM(
  applicationId: string,
  file: File
): Promise<SBOMUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    `${API_BASE}/api/v1/sbom/upload?application_id=${encodeURIComponent(applicationId)}`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new SBOMUploadError(body.detail ?? "Upload failed", response.status);
  }

  return response.json();
}

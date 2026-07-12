import { useCallback, useState } from "react";
import { SBOMUploadError, SBOMUploadResponse, uploadSBOM } from "../../api/sbomApi";

interface SBOMUploadProps {
  applicationId: string;
  onUploaded: (result: SBOMUploadResponse) => void;
}

type UploadState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "error"; message: string }
  | { status: "success"; result: SBOMUploadResponse };

/**
 * Drag-and-drop / click-to-browse SBOM uploader for a single application.
 * Deliberately dumb: it uploads, shows the parse summary, and hands the
 * result up via onUploaded. Graph visualization lives in Module 2's
 * components, not here.
 */
export function SBOMUpload({ applicationId, onUploaded }: SBOMUploadProps) {
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.endsWith(".json")) {
        setState({ status: "error", message: "Only JSON SBOM files (CycloneDX or SPDX) are supported." });
        return;
      }
      setState({ status: "uploading" });
      try {
        const result = await uploadSBOM(applicationId, file);
        setState({ status: "success", result });
        onUploaded(result);
      } catch (err) {
        const message = err instanceof SBOMUploadError ? err.message : "Unexpected error during upload.";
        setState({ status: "error", message });
      }
    },
    [applicationId, onUploaded]
  );

  const onDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragOver(false);
      const file = event.dataTransfer.files[0];
      if (file) void handleFile(file);
    },
    [handleFile]
  );

  const onFileInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (file) void handleFile(file);
    },
    [handleFile]
  );

  return (
    <div className="w-full">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors
          ${isDragOver ? "border-blue-500 bg-blue-50" : "border-slate-300 bg-slate-50"}`}
      >
        <p className="text-sm text-slate-600">
          Drag a CycloneDX or SPDX <span className="font-mono">.json</span> file here, or
        </p>
        <label className="mt-3 cursor-pointer rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
          Browse files
          <input type="file" accept=".json" className="hidden" onChange={onFileInputChange} />
        </label>
      </div>

      {state.status === "uploading" && (
        <p className="mt-3 text-sm text-slate-500">Parsing SBOM…</p>
      )}

      {state.status === "error" && (
        <div className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-700">{state.message}</div>
      )}

      {state.status === "success" && (
        <div className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">
          <p className="font-medium">
            Parsed as {state.result.format.toUpperCase()}
            {state.result.spec_version ? ` v${state.result.spec_version}` : ""}
          </p>
          <ul className="mt-1 list-inside list-disc">
            <li>{state.result.component_count} components extracted</li>
            <li>{state.result.direct_dependency_count} direct dependencies</li>
            <li>{state.result.edge_count} dependency edges</li>
          </ul>
          {state.result.warnings.length > 0 && (
            <details className="mt-2 text-amber-700">
              <summary className="cursor-pointer">
                {state.result.warnings.length} parser warning(s)
              </summary>
              <ul className="mt-1 list-inside list-disc">
                {state.result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

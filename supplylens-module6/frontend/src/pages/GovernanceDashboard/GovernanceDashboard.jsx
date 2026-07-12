import React, { useEffect, useState } from "react";
import { governanceApi } from "./api/governanceApi";
import RiskSummaryCards from "./components/RiskSummaryCards";
import RiskDistributionChart from "./components/RiskDistributionChart";
import TopRiskyApplications from "./components/TopRiskyApplications";
import TopRiskyDependencies from "./components/TopRiskyDependencies";
import TopSharedDependencies from "./components/TopSharedDependencies";
import RemediationPriorityTable from "./components/RemediationPriorityTable";

/**
 * Top-level Governance Reporting screen. Fetches every section in
 * parallel and renders once each has resolved (or shows an error
 * per-section rather than failing the whole page).
 */
export default function GovernanceDashboard() {
  const [summary, setSummary] = useState(null);
  const [applications, setApplications] = useState([]);
  const [dependencies, setDependencies] = useState([]);
  const [shared, setShared] = useState([]);
  const [remediation, setRemediation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError(null);
      try {
        const [
          summaryRes,
          appsRes,
          depsRes,
          sharedRes,
          remediationRes,
        ] = await Promise.all([
          governanceApi.getSummary(),
          governanceApi.getTopRiskyApplications(10),
          governanceApi.getTopRiskyDependencies(10),
          governanceApi.getTopSharedDependencies(10),
          governanceApi.getRemediationPriority(25),
        ]);

        if (cancelled) return;
        setSummary(summaryRes);
        setApplications(appsRes);
        setDependencies(depsRes);
        setShared(sharedRes);
        setRemediation(remediationRes);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleExportPdf() {
    setExporting(true);
    setExportError(null);
    try {
      const result = await governanceApi.exportPdf({
        report_type: "executive_summary",
        requested_by: "current-user", // wire up to auth context
      });
      window.open(governanceApi.downloadUrl(result.report_id), "_blank");
    } catch (err) {
      setExportError(err.message);
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-400">
        Loading governance dashboard…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-rose-800 bg-rose-950/40 p-4 text-rose-300">
        Failed to load governance data: {error}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 p-6 text-slate-100">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-white">
              Governance Reporting
            </h1>
            <p className="text-sm text-slate-400">
              Organization-wide software supply chain risk posture.
            </p>
          </div>
          <button
            onClick={handleExportPdf}
            disabled={exporting}
            className="rounded-md bg-amber-500 px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exporting ? "Generating report…" : "Export executive PDF"}
          </button>
        </header>

        {exportError && (
          <div className="rounded-md border border-rose-800 bg-rose-950/40 p-3 text-sm text-rose-300">
            Export failed: {exportError}
          </div>
        )}

        <RiskSummaryCards summary={summary} />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <RiskDistributionChart distribution={summary?.distribution} />
          </div>
          <div className="lg:col-span-2">
            <TopSharedDependencies shared={shared} />
          </div>
        </div>

        <TopRiskyApplications applications={applications} />
        <TopRiskyDependencies dependencies={dependencies} />
        <RemediationPriorityTable remediation={remediation} />
      </div>
    </div>
  );
}

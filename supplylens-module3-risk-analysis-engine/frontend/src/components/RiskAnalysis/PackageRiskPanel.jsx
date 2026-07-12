import React from "react";
import RiskBadge from "./RiskBadge";

/**
 * Explainable breakdown for a single package's risk profile.
 * Renders the `explanation` JSON from PackageRiskProfile verbatim so the
 * reasoning is always traceable to a specific CVE / version / license rule,
 * matching the "no black-box scoring" requirement in the project docs.
 */
export default function PackageRiskPanel({ profile }) {
  if (!profile) return null;
  const { explanation } = profile;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">Risk Breakdown</h3>
        <RiskBadge score={profile.vulnerability_score} />
      </div>

      <dl className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <dt className="text-slate-500">Vulnerability</dt>
          <dd className="font-mono font-medium">{profile.vulnerability_score.toFixed(1)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Patch Gap</dt>
          <dd className="font-mono font-medium">{profile.patch_gap_score.toFixed(1)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">License Risk</dt>
          <dd className="font-mono font-medium">{profile.license_risk_score.toFixed(1)}</dd>
        </div>
      </dl>

      <div className="mt-4 space-y-3 border-t border-slate-100 pt-3 text-sm text-slate-700">
        {explanation.worst_vulnerability && (
          <p>
            Worst known issue:{" "}
            <span className="font-mono">{explanation.worst_vulnerability.vuln_id}</span> (
            {explanation.worst_vulnerability.severity}, CVSS{" "}
            {explanation.worst_vulnerability.cvss_score.toFixed(1)})
          </p>
        )}
        <p>{explanation.patch_reasoning}</p>
        <p>{explanation.license_reasoning}</p>

        {explanation.all_vulnerabilities?.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-indigo-600">
              View all {explanation.all_vulnerabilities.length} known vulnerabilities
            </summary>
            <ul className="mt-2 space-y-1 pl-4 text-xs">
              {explanation.all_vulnerabilities.map((v) => (
                <li key={v.vuln_id} className="font-mono">
                  {v.vuln_id} — CVSS {v.cvss_score.toFixed(1)} ({v.severity})
                  {v.fixed_version ? ` — fixed in ${v.fixed_version}` : " — no fix yet"}
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}

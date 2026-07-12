import React from "react";

function scoreColor(score) {
  if (score >= 90) return "text-rose-500";
  if (score >= 70) return "text-orange-400";
  if (score >= 40) return "text-amber-400";
  return "text-emerald-400";
}

export default function TopRiskyApplications({ applications }) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        Top Risky Applications
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400">
              <th className="py-2 pr-4 font-medium">Application</th>
              <th className="py-2 pr-4 font-medium">Criticality</th>
              <th className="py-2 pr-4 font-medium">Risk Score</th>
              <th className="py-2 pr-4 font-medium">Blast Radius</th>
              <th className="py-2 font-medium">SPOF Count</th>
            </tr>
          </thead>
          <tbody>
            {(applications ?? []).map((app) => (
              <tr
                key={app.application_id}
                className="border-b border-slate-800 text-slate-200 last:border-0"
              >
                <td className="py-2 pr-4">{app.application_name}</td>
                <td className="py-2 pr-4 text-slate-400">
                  {app.business_criticality}
                </td>
                <td className={`py-2 pr-4 font-mono font-semibold ${scoreColor(app.risk_score)}`}>
                  {app.risk_score.toFixed(1)}
                </td>
                <td className="py-2 pr-4 font-mono">{app.blast_radius}</td>
                <td className="py-2 font-mono">{app.spof_count}</td>
              </tr>
            ))}
            {(!applications || applications.length === 0) && (
              <tr>
                <td colSpan={5} className="py-6 text-center text-slate-500">
                  No applications scored yet — ingest an SBOM to populate this
                  view.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

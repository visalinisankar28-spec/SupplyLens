import React from "react";

export default function TopRiskyDependencies({ dependencies }) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        Top Risky Dependencies
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400">
              <th className="py-2 pr-4 font-medium">Dependency</th>
              <th className="py-2 pr-4 font-medium">Ecosystem</th>
              <th className="py-2 pr-4 font-medium">Risk Score</th>
              <th className="py-2 pr-4 font-medium">Max CVSS</th>
              <th className="py-2 pr-4 font-medium">Patch</th>
              <th className="py-2 font-medium">Apps Affected</th>
            </tr>
          </thead>
          <tbody>
            {(dependencies ?? []).map((dep) => (
              <tr
                key={dep.dependency_id}
                className="border-b border-slate-800 text-slate-200 last:border-0"
              >
                <td className="py-2 pr-4">{dep.dependency_name}</td>
                <td className="py-2 pr-4 text-slate-400">{dep.ecosystem}</td>
                <td className="py-2 pr-4 font-mono font-semibold text-orange-400">
                  {dep.risk_score.toFixed(1)}
                </td>
                <td className="py-2 pr-4 font-mono">{dep.max_cvss.toFixed(1)}</td>
                <td className="py-2 pr-4">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      dep.patch_available
                        ? "bg-emerald-900/50 text-emerald-300"
                        : "bg-rose-900/50 text-rose-300"
                    }`}
                  >
                    {dep.patch_available ? "Available" : "None"}
                  </span>
                </td>
                <td className="py-2 font-mono">{dep.affected_application_count}</td>
              </tr>
            ))}
            {(!dependencies || dependencies.length === 0) && (
              <tr>
                <td colSpan={6} className="py-6 text-center text-slate-500">
                  No dependency risk data available yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

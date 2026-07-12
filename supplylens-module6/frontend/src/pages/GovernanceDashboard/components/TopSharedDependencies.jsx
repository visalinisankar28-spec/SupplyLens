import React from "react";

export default function TopSharedDependencies({ shared }) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        Top Shared Dependencies
        <span className="ml-2 font-normal normal-case text-slate-500">
          — concentration / single-point-of-failure candidates
        </span>
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400">
              <th className="py-2 pr-4 font-medium">Dependency</th>
              <th className="py-2 pr-4 font-medium">Ecosystem</th>
              <th className="py-2 pr-4 font-medium"># Applications</th>
              <th className="py-2 font-medium">Concentration</th>
            </tr>
          </thead>
          <tbody>
            {(shared ?? []).map((dep) => (
              <tr
                key={dep.dependency_id}
                className="border-b border-slate-800 text-slate-200 last:border-0"
                title={dep.application_names?.join(", ")}
              >
                <td className="py-2 pr-4">{dep.dependency_name}</td>
                <td className="py-2 pr-4 text-slate-400">{dep.ecosystem}</td>
                <td className="py-2 pr-4 font-mono">{dep.application_count}</td>
                <td className="py-2">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-700">
                      <div
                        className="h-full rounded-full bg-amber-400"
                        style={{ width: `${dep.concentration_ratio * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-xs text-slate-400">
                      {(dep.concentration_ratio * 100).toFixed(0)}%
                    </span>
                  </div>
                </td>
              </tr>
            ))}
            {(!shared || shared.length === 0) && (
              <tr>
                <td colSpan={4} className="py-6 text-center text-slate-500">
                  No shared dependencies detected across applications yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

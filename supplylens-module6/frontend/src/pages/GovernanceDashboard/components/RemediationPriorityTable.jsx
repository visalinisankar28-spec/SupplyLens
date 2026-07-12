import React from "react";

export default function RemediationPriorityTable({ remediation }) {
  const items = remediation?.items ?? [];

  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
          Remediation Priority
        </h3>
        {remediation?.generated_at && (
          <span className="text-xs text-slate-500">
            Generated {new Date(remediation.generated_at).toLocaleString()}
          </span>
        )}
      </div>
      <ol className="space-y-2">
        {items.map((item) => (
          <li
            key={item.dependency_id}
            className="flex items-start gap-3 rounded-md border border-slate-700/40 bg-slate-900/40 p-3"
          >
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-700 font-mono text-xs font-semibold text-slate-200">
              {item.rank}
            </span>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="font-medium text-slate-100">
                  {item.dependency_name}
                </span>
                <span className="font-mono text-sm font-semibold text-amber-400">
                  priority {item.priority_score.toFixed(2)}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400">{item.explanation}</p>
            </div>
          </li>
        ))}
        {items.length === 0 && (
          <li className="py-6 text-center text-slate-500">
            Nothing to remediate right now — the queue is clear.
          </li>
        )}
      </ol>
    </div>
  );
}

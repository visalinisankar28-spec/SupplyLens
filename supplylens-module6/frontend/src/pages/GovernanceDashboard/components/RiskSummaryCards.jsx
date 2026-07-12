import React from "react";

/**
 * Four/five-up KPI strip at the top of the dashboard.
 * Values are already-computed numbers from GET /governance/summary —
 * this component only renders, it does not calculate anything.
 */
export default function RiskSummaryCards({ summary }) {
  if (!summary) return null;

  const cards = [
    {
      label: "Applications",
      value: summary.total_applications,
      accent: "text-slate-200",
    },
    {
      label: "Dependencies",
      value: summary.total_dependencies,
      accent: "text-slate-200",
    },
    {
      label: "Shared Dependencies",
      value: summary.total_shared_dependencies,
      accent: "text-amber-400",
    },
    {
      label: "Open Vulnerabilities",
      value: summary.total_open_vulnerabilities,
      accent: "text-rose-400",
    },
    {
      label: "Critical Applications",
      value: summary.critical_application_count,
      accent: "text-rose-500",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4"
        >
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
            {card.label}
          </p>
          <p className={`mt-2 font-mono text-2xl font-semibold ${card.accent}`}>
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}

import React from "react";

/**
 * Colored severity chip for a CVSS-derived vulnerability score.
 * Bands mirror service.py's _severity_from_cvss so the UI and backend
 * never disagree on what "critical" means.
 */
const BANDS = [
  { max: Infinity, min: 9.0, label: "CRITICAL", classes: "bg-red-100 text-red-800 border-red-300" },
  { max: 9.0, min: 7.0, label: "HIGH", classes: "bg-orange-100 text-orange-800 border-orange-300" },
  { max: 7.0, min: 4.0, label: "MEDIUM", classes: "bg-yellow-100 text-yellow-800 border-yellow-300" },
  { max: 4.0, min: 0.0001, label: "LOW", classes: "bg-blue-100 text-blue-800 border-blue-300" },
  { max: 0.0001, min: 0, label: "CLEAN", classes: "bg-green-100 text-green-800 border-green-300" },
];

export default function RiskBadge({ score = 0 }) {
  const band = BANDS.find((b) => score >= b.min && score < b.max) || BANDS[BANDS.length - 1];

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${band.classes}`}
      title={`CVSS ${score.toFixed(1)}`}
    >
      {band.label}
      <span className="font-mono font-normal opacity-70">{score.toFixed(1)}</span>
    </span>
  );
}

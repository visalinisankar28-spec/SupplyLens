import React from "react";

const riskColor = (score) => {
  if (score >= 7.5) return "text-red-600 border-red-200 bg-red-50";
  if (score >= 5.0) return "text-orange-600 border-orange-200 bg-orange-50";
  if (score >= 2.5) return "text-yellow-600 border-yellow-200 bg-yellow-50";
  return "text-green-600 border-green-200 bg-green-50";
};

const COMPONENTS = [
  { key: "vulnerability_component", label: "Vulnerability", weightKey: "vulnerability" },
  { key: "repo_health_component", label: "Repo Health", weightKey: "repo_health" },
  { key: "license_component", label: "License", weightKey: "license" },
  { key: "centrality_score", label: "Centrality", weightKey: "centrality" },
  { key: "business_criticality_score", label: "Business Criticality", weightKey: "business_crit" },
];

/**
 * Full explainable breakdown of one package's Enterprise Risk Score, as
 * returned by GET /api/v1/enterprise-intelligence/enterprise-risk-scores
 */
export default function EnterpriseRiskScoreCard({ profile }) {
  if (!profile) return null;
  const weights = profile.explanation?.weights || {};

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">Enterprise Risk Score</h3>
        <span
          className={`rounded-full border px-3 py-1 text-sm font-bold ${riskColor(
            profile.enterprise_risk_score
          )}`}
        >
          {profile.enterprise_risk_score.toFixed(1)} / 10
        </span>
      </div>

      <div className="space-y-2">
        {COMPONENTS.map(({ key, label, weightKey }) => {
          const value = profile[key] ?? 0;
          const weight = weights[weightKey] ?? 0;
          return (
            <div key={key} className="flex items-center gap-3 text-xs">
              <span className="w-36 shrink-0 text-slate-500">
                {label} <span className="text-slate-400">(×{weight.toFixed(2)})</span>
              </span>
              <div className="h-2 flex-1 rounded-full bg-slate-100">
                <div
                  className="h-2 rounded-full bg-indigo-500"
                  style={{ width: `${Math.min(100, (value / 10) * 100)}%` }}
                />
              </div>
              <span className="w-10 text-right font-mono font-medium text-slate-700">
                {value.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-600">
        <p>{profile.explanation?.concentration_reasoning}</p>
        <p>{profile.explanation?.centrality_reasoning}</p>
        <p>{profile.explanation?.business_criticality_reasoning}</p>
      </div>
    </div>
  );
}

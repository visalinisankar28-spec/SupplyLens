import React from "react";

const scoreColor = (score) => {
  if (score >= 7.5) return "text-red-600 border-red-200 bg-red-50";
  if (score >= 5.0) return "text-orange-600 border-orange-200 bg-orange-50";
  if (score >= 2.5) return "text-yellow-600 border-yellow-200 bg-yellow-50";
  return "text-green-600 border-green-200 bg-green-50";
};

/**
 * Compact per-package repository health summary, driven by
 * GET /api/v1/repo-intelligence/packages/{id}/profile
 */
export default function RepoHealthCard({ profile }) {
  if (!profile) return null;

  const {
    repo_url,
    stars,
    forks,
    contributors_count,
    scorecard_overall_score,
    repo_health_score,
    explanation,
  } = profile;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between">
        <div>
          <a
            href={repo_url}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-semibold text-indigo-600 hover:underline"
          >
            {repo_url.replace("https://github.com/", "")}
          </a>
          <p className="mt-1 text-xs text-slate-500">
            ★ {stars ?? "—"} · ⑂ {forks ?? "—"} · {contributors_count ?? "—"} contributors
          </p>
        </div>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${scoreColor(
            repo_health_score
          )}`}
        >
          Health risk {repo_health_score.toFixed(1)}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-3 text-xs text-slate-600 sm:grid-cols-4">
        <div>
          <dt className="text-slate-400">Scorecard</dt>
          <dd className="font-mono font-medium text-slate-800">
            {scorecard_overall_score != null ? scorecard_overall_score.toFixed(1) : "n/a"}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Maintenance</dt>
          <dd className="font-mono font-medium text-slate-800">
            {profile.maintenance_score.toFixed(1)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Activity</dt>
          <dd className="font-mono font-medium text-slate-800">
            {profile.activity_score.toFixed(1)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-400">Bus Factor</dt>
          <dd className="font-mono font-medium text-slate-800">
            {profile.bus_factor_score.toFixed(1)}
          </dd>
        </div>
      </dl>

      <div className="mt-3 space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-600">
        <p>{explanation.maintenance_reasoning}</p>
        <p>{explanation.bus_factor_reasoning}</p>
      </div>
    </div>
  );
}

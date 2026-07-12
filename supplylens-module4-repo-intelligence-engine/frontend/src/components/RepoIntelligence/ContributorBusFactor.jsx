import React, { useMemo } from "react";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = ["#dc2626", "#94a3b8"]; // top contributor vs everyone else

/**
 * Donut chart showing a single package's commit concentration —
 * "top contributor" vs "everyone else". Flags single points of failure
 * when the top contributor's share crosses the alert threshold used by
 * GET /api/v1/repo-intelligence/applications/{id}/single-points-of-failure
 */
export default function ContributorBusFactor({ profile, alertThreshold = 75 }) {
  const share = profile?.top_contributor_commit_share;

  const data = useMemo(() => {
    if (share == null) return [];
    return [
      { name: "Top contributor", value: share },
      { name: "Everyone else", value: Math.max(0, 100 - share) },
    ];
  }, [share]);

  if (share == null) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-slate-200 bg-white text-sm text-slate-400">
        Contributor data unavailable
      </div>
    );
  }

  const isSinglePointOfFailure = share >= alertThreshold;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="name"
              innerRadius={45}
              outerRadius={70}
              paddingAngle={2}
            >
              {data.map((entry, index) => (
                <Cell key={entry.name} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => `${value.toFixed(1)}%`} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
      {isSinglePointOfFailure && (
        <p className="mt-2 rounded bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700">
          ⚠ Single point of failure — {share.toFixed(0)}% of commits from one contributor.
        </p>
      )}
    </div>
  );
}

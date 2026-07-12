import React, { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

/**
 * Plots every package's last-commit / last-release recency against its
 * maintenance risk, across an application's full repository profile list.
 * Input: array from GET /api/v1/repo-intelligence/applications/{id}/profiles
 */
export default function MaintenanceTimeline({ profiles = [] }) {
  const data = useMemo(() => {
    const now = Date.now();
    return profiles
      .filter((p) => p.last_commit_at || p.last_release_at)
      .map((p) => {
        const lastActivity = new Date(p.last_commit_at || p.last_release_at).getTime();
        const daysStale = Math.round((now - lastActivity) / (1000 * 60 * 60 * 24));
        return {
          name: p.repo_url.replace("https://github.com/", ""),
          daysStale,
          maintenanceScore: p.maintenance_score,
          repoHealthScore: p.repo_health_score,
        };
      });
  }, [profiles]);

  return (
    <div className="h-72 w-full rounded-lg border border-slate-200 bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            type="number"
            dataKey="daysStale"
            name="Days since last activity"
            tick={{ fontSize: 11 }}
            label={{ value: "Days since last activity", position: "insideBottom", offset: -5, fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="maintenanceScore"
            name="Maintenance risk"
            domain={[0, 10]}
            tick={{ fontSize: 11 }}
            label={{ value: "Maintenance risk", angle: -90, position: "insideLeft", fontSize: 11 }}
          />
          <ZAxis type="number" dataKey="repoHealthScore" range={[60, 300]} name="Repo health risk" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            formatter={(value, name) => [value, name]}
            labelFormatter={() => ""}
            content={({ payload }) => {
              if (!payload || payload.length === 0) return null;
              const p = payload[0].payload;
              return (
                <div className="rounded border border-slate-200 bg-white p-2 text-xs shadow">
                  <p className="font-semibold">{p.name}</p>
                  <p>{p.daysStale} days since last activity</p>
                  <p>Maintenance risk: {p.maintenanceScore.toFixed(1)}</p>
                </div>
              );
            }}
          />
          <Legend />
          <Scatter name="Packages" data={data} fill="#4f46e5" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

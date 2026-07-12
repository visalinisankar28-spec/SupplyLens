import React, { useMemo } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

/**
 * Top shared dependencies by how many applications use them — the most
 * direct visualization of "why enterprise-wide correlation matters".
 * Input: GET /api/v1/enterprise-intelligence/shared-dependencies?min_apps=2
 */
export default function SharedDependencyConcentration({ profiles = [], packageNames = {}, top = 10 }) {
  const data = useMemo(() => {
    return [...profiles]
      .sort((a, b) => b.application_count - a.application_count)
      .slice(0, top)
      .map((p) => ({
        name: packageNames[p.package_id] || p.package_id.slice(0, 8),
        applications: p.application_count,
        concentration: Math.round(p.concentration_ratio * 100),
      }));
  }, [profiles, packageNames, top]);

  return (
    <div className="h-80 w-full rounded-lg border border-slate-200 bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
          <Tooltip
            formatter={(value, key) =>
              key === "applications" ? [`${value} applications`, "Used by"] : [`${value}%`, "Concentration"]
            }
          />
          <Bar dataKey="applications" fill="#4f46e5" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

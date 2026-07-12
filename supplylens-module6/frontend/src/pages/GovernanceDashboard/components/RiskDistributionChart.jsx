import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const BUCKET_COLORS = {
  Low: "#22c55e",
  Medium: "#eab308",
  High: "#f97316",
  Critical: "#e11d48",
};

export default function RiskDistributionChart({ distribution }) {
  if (!distribution || distribution.length === 0) return null;

  const data = distribution.map((d) => ({
    bucket: d.bucket,
    count: d.count,
    percentage: d.percentage,
  }));

  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-300">
        Risk Distribution
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="bucket" stroke="#94a3b8" fontSize={12} />
          <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f172a",
              border: "1px solid #334155",
              borderRadius: 8,
              color: "#e2e8f0",
            }}
            formatter={(value, _name, props) => [
              `${value} apps (${props.payload.percentage}%)`,
              "Count",
            ]}
          />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.bucket} fill={BUCKET_COLORS[entry.bucket]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

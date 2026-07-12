import { useEffect, useMemo, useState } from "react";
import { getSbomHealth } from "../api/healthApi";
import type { HealthCategory, HealthProfile, SbomHealthSummary } from "../types/health";

interface Props {
  sbomId: string;
}

/** Maps each health category to a badge color - deliberately not "red = bad, green = good"
 *  security-alert colors, since this module measures sustainability, not vulnerability. */
const CATEGORY_STYLES: Record<HealthCategory, { background: string; text: string }> = {
  Healthy: { background: "#1F4B3F", text: "#7FE8B8" },
  Stable: { background: "#1E3A4C", text: "#7FC8E8" },
  "Needs Attention": { background: "#4C3B1E", text: "#E8C87F" },
  "High Maintenance Risk": { background: "#4C1E1E", text: "#E87F7F" },
};

function CategoryBadge({ category }: { category: HealthCategory }) {
  const style = CATEGORY_STYLES[category];
  return (
    <span
      style={{
        backgroundColor: style.background,
        color: style.text,
        padding: "2px 10px",
        borderRadius: "4px",
        fontSize: "0.75rem",
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {category}
    </span>
  );
}

function ComponentRow({ profile }: { profile: HealthProfile }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        onClick={() => setExpanded((prev) => !prev)}
        style={{ cursor: "pointer", borderBottom: "1px solid #2A2F3A" }}
      >
        <td style={{ padding: "10px 12px", fontFamily: "monospace", fontSize: "0.85rem" }}>
          {profile.repo_url ?? "(repository unresolved)"}
        </td>
        <td style={{ padding: "10px 12px" }}>
          <CategoryBadge category={profile.dhi_category} />
        </td>
        <td style={{ padding: "10px 12px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
          {profile.dhi_score.toFixed(1)}
        </td>
        <td style={{ padding: "10px 12px", textAlign: "right" }}>
          {profile.contributors_count ?? "—"}
        </td>
        <td style={{ padding: "10px 12px", textAlign: "right" }}>
          {profile.days_since_last_release !== null ? `${profile.days_since_last_release}d ago` : "—"}
        </td>
      </tr>
      {expanded && profile.explanation.length > 0 && (
        <tr style={{ backgroundColor: "#12151C" }}>
          <td colSpan={5} style={{ padding: "8px 12px 14px 12px" }}>
            <div style={{ fontSize: "0.8rem", color: "#9AA3B2" }}>
              <strong style={{ color: "#C8CED9" }}>Why this rating:</strong>
              <ul style={{ margin: "6px 0 0 18px" }}>
                {profile.explanation.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/**
 * Displays the Dependency Health summary for one SBOM: an aggregate
 * breakdown by category, followed by a sortable, expandable table of every
 * analyzed component.
 */
export function DependencyHealthTable({ sbomId }: Props) {
  const [summary, setSummary] = useState<SbomHealthSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getSbomHealth(sbomId)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sbomId]);

  const sortedProfiles = useMemo(
    () => (summary ? [...summary.profiles].sort((a, b) => a.dhi_score - b.dhi_score) : []),
    [summary]
  );

  if (loading) {
    return <p style={{ color: "#9AA3B2" }}>Loading dependency health data…</p>;
  }

  if (error) {
    return (
      <div style={{ color: "#E87F7F" }}>
        Could not load dependency health data: {error}
      </div>
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <section style={{ fontFamily: "system-ui, sans-serif", color: "#E4E7EC" }}>
      <div style={{ display: "flex", gap: "24px", marginBottom: "20px", flexWrap: "wrap" }}>
        <SummaryStat label="Components analyzed" value={`${summary.analyzed_components} / ${summary.total_components}`} />
        <SummaryStat label="Average DHI score" value={summary.average_dhi_score.toFixed(1)} />
        {Object.entries(summary.category_breakdown).map(([category, count]) => (
          <SummaryStat key={category} label={category} value={String(count)} />
        ))}
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ textAlign: "left", borderBottom: "2px solid #2A2F3A", color: "#9AA3B2" }}>
            <th style={{ padding: "8px 12px" }}>Repository</th>
            <th style={{ padding: "8px 12px" }}>Health Category</th>
            <th style={{ padding: "8px 12px", textAlign: "right" }}>DHI Score</th>
            <th style={{ padding: "8px 12px", textAlign: "right" }}>Contributors</th>
            <th style={{ padding: "8px 12px", textAlign: "right" }}>Last Release</th>
          </tr>
        </thead>
        <tbody>
          {sortedProfiles.map((profile) => (
            <ComponentRow key={profile.component_id} profile={profile} />
          ))}
        </tbody>
      </table>
    </section>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: "0.7rem", color: "#9AA3B2", textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ fontSize: "1.4rem", fontWeight: 600 }}>{value}</div>
    </div>
  );
}

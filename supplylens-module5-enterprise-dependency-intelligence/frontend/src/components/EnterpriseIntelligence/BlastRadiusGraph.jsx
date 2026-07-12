import React, { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

/**
 * Renders the "if this package is compromised, here's what goes down"
 * graph: the package in the center, affected applications radiating
 * outward. Input: GET /api/v1/enterprise-intelligence/blast-radius/{package_id}
 *
 * Props:
 *   packageLabel: display name for the central node (e.g. "left-pad@1.3.0")
 *   blastRadius: { affected_application_ids: string[], blast_radius_app_count, total_applications }
 *   applicationNames: optional { [applicationId]: displayName } lookup
 */
export default function BlastRadiusGraph({ packageLabel, blastRadius, applicationNames = {} }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !blastRadius) return;

    const elements = [
      {
        data: { id: "package", label: packageLabel },
        classes: "package-node",
      },
      ...blastRadius.affected_application_ids.map((appId) => ({
        data: {
          id: appId,
          label: applicationNames[appId] || appId.slice(0, 8),
        },
        classes: "app-node",
      })),
      ...blastRadius.affected_application_ids.map((appId) => ({
        data: { id: `edge-${appId}`, source: "package", target: appId },
      })),
    ];

    cyRef.current?.destroy();
    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      layout: { name: "concentric", concentric: (n) => (n.data("id") === "package" ? 10 : 1), minNodeSpacing: 40 },
      style: [
        {
          selector: ".package-node",
          style: {
            "background-color": "#dc2626",
            label: "data(label)",
            color: "#1e293b",
            "font-size": 12,
            "font-weight": "bold",
            width: 50,
            height: 50,
            "text-valign": "bottom",
            "text-margin-y": 6,
          },
        },
        {
          selector: ".app-node",
          style: {
            "background-color": "#4f46e5",
            label: "data(label)",
            color: "#475569",
            "font-size": 10,
            width: 28,
            height: 28,
            "text-valign": "bottom",
            "text-margin-y": 4,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#cbd5e1",
            "curve-style": "bezier",
            "target-arrow-shape": "none",
          },
        },
      ],
    });

    return () => cyRef.current?.destroy();
  }, [packageLabel, blastRadius, applicationNames]);

  if (!blastRadius) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-semibold text-slate-800">Blast Radius</span>
        <span className="text-red-600">
          {blastRadius.blast_radius_app_count} of {blastRadius.total_applications} applications affected
        </span>
      </div>
      <div ref={containerRef} style={{ width: "100%", height: 320 }} />
    </div>
  );
}

"""
Executive PDF report generator for Governance Reporting.

Uses ReportLab (pure Python, no headless-browser dependency — keeps the
container image small and the build deterministic) to render a printable
report suitable for an audit trail or board pack.

No AI/LLM involvement in report generation — every figure comes straight
from the aggregation layer in service.py, so the PDF is exactly as
explainable as the dashboard.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.modules.governance.schemas import (
    GovernanceSummary,
    RemediationPriorityResponse,
    RiskyApplication,
    RiskyDependency,
    SharedDependency,
)

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle(
    "SupplyLensTitle", parent=_STYLES["Title"], textColor=colors.HexColor("#1e293b")
)
_SECTION_STYLE = ParagraphStyle(
    "SupplyLensSection",
    parent=_STYLES["Heading2"],
    textColor=colors.HexColor("#1e293b"),
    spaceBefore=18,
    spaceAfter=8,
)
_BODY_STYLE = _STYLES["BodyText"]

_TABLE_HEADER_BG = colors.HexColor("#1e293b")
_TABLE_ROW_ALT_BG = colors.HexColor("#f1f5f9")


def _styled_table(data: list[list[str]], col_widths: list[float] | None = None) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _TABLE_ROW_ALT_BG]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def build_executive_pdf(
    output_path: Path,
    summary: GovernanceSummary,
    top_applications: list[RiskyApplication],
    top_dependencies: list[RiskyDependency],
    top_shared: list[SharedDependency],
    remediation: RemediationPriorityResponse,
) -> None:
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
    )

    story = []

    story.append(Paragraph("SupplyLens — Executive Risk Report", _TITLE_STYLE))
    story.append(
        Paragraph(
            f"Generated {summary.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            _BODY_STYLE,
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    # --- Portfolio Summary -------------------------------------------------
    story.append(Paragraph("Portfolio Summary", _SECTION_STYLE))
    summary_data = [
        ["Metric", "Value"],
        ["Total Applications", str(summary.total_applications)],
        ["Total Dependencies", str(summary.total_dependencies)],
        ["Shared Dependencies (used by 2+ apps)", str(summary.total_shared_dependencies)],
        ["Open Vulnerabilities (unpatched)", str(summary.total_open_vulnerabilities)],
        ["Average Enterprise Risk Score", f"{summary.average_risk_score:.1f}"],
        ["Median Enterprise Risk Score", f"{summary.median_risk_score:.1f}"],
        ["Critical Applications", str(summary.critical_application_count)],
    ]
    story.append(_styled_table(summary_data, col_widths=[9 * cm, 6 * cm]))
    story.append(Spacer(1, 0.3 * cm))

    dist_data = [["Risk Bucket", "Applications", "% of Portfolio"]]
    for b in summary.distribution:
        dist_data.append([b.bucket.value, str(b.count), f"{b.percentage:.1f}%"])
    story.append(_styled_table(dist_data, col_widths=[5 * cm, 5 * cm, 5 * cm]))

    # --- Top Risky Applications ---------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Top Risky Applications", _SECTION_STYLE))
    app_data = [["Application", "Criticality", "Risk Score", "Blast Radius", "SPOF Count"]]
    for a in top_applications:
        app_data.append(
            [
                a.application_name,
                a.business_criticality,
                f"{a.risk_score:.1f}",
                str(a.blast_radius),
                str(a.spof_count),
            ]
        )
    story.append(_styled_table(app_data, col_widths=[5.5 * cm, 3 * cm, 2.5 * cm, 3 * cm, 2.5 * cm]))

    # --- Top Risky Dependencies ---------------------------------------------
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Top Risky Dependencies", _SECTION_STYLE))
    dep_data = [["Dependency", "Ecosystem", "Risk Score", "Max CVSS", "Patch?", "Apps Affected"]]
    for d in top_dependencies:
        dep_data.append(
            [
                d.dependency_name,
                d.ecosystem,
                f"{d.risk_score:.1f}",
                f"{d.max_cvss:.1f}",
                "Yes" if d.patch_available else "No",
                str(d.affected_application_count),
            ]
        )
    story.append(
        _styled_table(dep_data, col_widths=[4.5 * cm, 2.5 * cm, 2.2 * cm, 2.2 * cm, 1.8 * cm, 2.8 * cm])
    )

    # --- Top Shared Dependencies ---------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Top Shared Dependencies (Concentration Risk)", _SECTION_STYLE))
    shared_data = [["Dependency", "Ecosystem", "# Applications", "Concentration"]]
    for s in top_shared:
        shared_data.append(
            [
                s.dependency_name,
                s.ecosystem,
                str(s.application_count),
                f"{s.concentration_ratio * 100:.0f}%",
            ]
        )
    story.append(_styled_table(shared_data, col_widths=[5 * cm, 3 * cm, 3.5 * cm, 3.5 * cm]))

    # --- Remediation Priority -------------------------------------------------
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Remediation Priority", _SECTION_STYLE))
    remediation_data = [["#", "Dependency", "Priority Score", "Explanation"]]
    for item in remediation.items:
        remediation_data.append(
            [str(item.rank), item.dependency_name, f"{item.priority_score:.2f}", item.explanation]
        )
    story.append(_styled_table(remediation_data, col_widths=[1 * cm, 4 * cm, 3 * cm, 7 * cm]))

    story.append(Spacer(1, 1 * cm))
    story.append(
        Paragraph(
            "All scores in this report are computed deterministically from stored "
            "vulnerability, repository health, and dependency graph data. "
            "No generative or black-box model is used to produce risk figures.",
            _BODY_STYLE,
        )
    )

    doc.build(story)

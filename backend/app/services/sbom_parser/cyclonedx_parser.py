"""
CycloneDX (JSON) parser.

Spec reference (structure we rely on): a CycloneDX document has
  - bomFormat == "CycloneDX"
  - specVersion, e.g. "1.5"
  - metadata.component  -> the root/application component (optional but common)
  - components[]        -> flat list of all components, each with a bom-ref
  - dependencies[]       -> [{ "ref": <bom-ref>, "dependsOn": [<bom-ref>, ...] }]

We do NOT assume every component appears in `dependencies` (some tools omit
leaf nodes with no children) — absence from `dependencies` just means "no
outgoing edges", not "malformed document".
"""

from __future__ import annotations

from typing import Any

from app.schemas.sbom import (
    ComponentType,
    ParsedComponent,
    ParsedDependencyEdge,
    ParsedSBOM,
    SBOMFormat,
)
from app.services.sbom_parser.base import SBOMParseError, SBOMParser

_CDX_TYPE_MAP = {
    "library": ComponentType.LIBRARY,
    "application": ComponentType.APPLICATION,
    "framework": ComponentType.FRAMEWORK,
}


def _extract_ecosystem_from_purl(purl: str | None) -> str | None:
    """purl format: pkg:<type>/<namespace>/<name>@<version>?<qualifiers>"""
    if not purl or not purl.startswith("pkg:"):
        return None
    remainder = purl[len("pkg:"):]
    return remainder.split("/", 1)[0] or None


def _extract_license(component: dict[str, Any]) -> str | None:
    """CycloneDX licenses can be declared multiple ways:
    licenses: [{ "license": { "id": "MIT" } }]
    licenses: [{ "license": { "name": "Custom License Text" } }]
    licenses: [{ "expression": "Apache-2.0 OR MIT" }]
    We prefer an SPDX expression/id when present; fall back to name.
    """
    licenses = component.get("licenses") or []
    ids: list[str] = []
    for entry in licenses:
        if "expression" in entry:
            ids.append(entry["expression"])
        elif "license" in entry:
            lic = entry["license"]
            ids.append(lic.get("id") or lic.get("name") or "UNKNOWN")
    if not ids:
        return None
    return " AND ".join(ids)


def _extract_repo_url(component: dict[str, Any]) -> str | None:
    for ref in component.get("externalReferences", []):
        if ref.get("type") in ("vcs", "distribution", "website"):
            return ref.get("url")
    return None


class CycloneDXParser(SBOMParser):
    def can_parse(self, raw: dict[str, Any]) -> bool:
        return raw.get("bomFormat") == "CycloneDX" or "specVersion" in raw and "components" in raw

    def parse(self, raw: dict[str, Any]) -> ParsedSBOM:
        if "components" not in raw:
            raise SBOMParseError("CycloneDX document is missing required 'components' array")

        warnings: list[str] = []
        spec_version = raw.get("specVersion")

        root_ref: str | None = None
        components: list[ParsedComponent] = []

        metadata_component = (raw.get("metadata") or {}).get("component")
        if metadata_component:
            root_ref = metadata_component.get("bom-ref") or metadata_component.get("name")

        direct_refs: set[str] = set()
        dependencies_section = raw.get("dependencies", [])
        if root_ref:
            for dep in dependencies_section:
                if dep.get("ref") == root_ref:
                    direct_refs.update(dep.get("dependsOn", []))

        for comp in raw["components"]:
            ref = comp.get("bom-ref")
            name = comp.get("name")
            if not name:
                warnings.append("Skipped a component with no 'name' field")
                continue
            if not ref:
                # Not spec-compliant, but tolerate it — fall back to name@version
                ref = f"{name}@{comp.get('version', 'unknown')}"
                warnings.append(f"Component '{name}' missing bom-ref; synthesized ref '{ref}'")

            purl = comp.get("purl")
            components.append(
                ParsedComponent(
                    ref=ref,
                    name=name,
                    version=comp.get("version"),
                    purl=purl,
                    ecosystem=_extract_ecosystem_from_purl(purl),
                    license=_extract_license(comp),
                    component_type=_CDX_TYPE_MAP.get(comp.get("type", ""), ComponentType.UNKNOWN),
                    is_direct=ref in direct_refs,
                    source_repo_url=_extract_repo_url(comp),
                )
            )

        known_refs = {c.ref for c in components}
        if root_ref:
            known_refs.add(root_ref)

        edges: list[ParsedDependencyEdge] = []
        for dep in dependencies_section:
            source = dep.get("ref")
            if source is None:
                continue
            for target in dep.get("dependsOn", []):
                if source not in known_refs:
                    warnings.append(f"Dependency edge references unknown source '{source}'")
                    continue
                if target not in known_refs:
                    warnings.append(f"Dependency edge references unknown target '{target}'")
                    continue
                edges.append(ParsedDependencyEdge(source_ref=source, target_ref=target))

        if not direct_refs and root_ref is None:
            warnings.append(
                "No metadata.component found — unable to determine which components are "
                "direct dependencies of the application itself; all components will be "
                "treated as indeterminate depth until the Dependency Graph Engine resolves it."
            )

        return ParsedSBOM(
            format=SBOMFormat.CYCLONEDX,
            spec_version=spec_version,
            root_component_ref=root_ref,
            components=components,
            edges=edges,
            warnings=warnings,
        )

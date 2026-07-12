"""
SPDX (JSON) parser.

Spec reference (structure we rely on): an SPDX document has
  - spdxVersion, e.g. "SPDX-2.3"
  - packages[]       -> each with SPDXID, name, versionInfo, licenseConcluded/licenseDeclared
  - relationships[]  -> [{ spdxElementId, relatedSpdxElement, relationshipType }]

Unlike CycloneDX, SPDX relationships are typed (DEPENDS_ON, DESCRIBES, etc.)
and can point in either direction depending on relationshipType, so we
normalize them carefully rather than assuming a fixed direction.
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

# Relationship types where spdxElementId is the DEPENDANT (source) and
# relatedSpdxElement is the DEPENDENCY (target) — i.e. edge points source -> target.
_FORWARD_DEPENDENCY_TYPES = {"DEPENDS_ON", "CONTAINS"}
# Relationship types where the direction is reversed relative to the above.
_REVERSE_DEPENDENCY_TYPES = {"DEPENDENCY_OF", "CONTAINED_BY"}
_DESCRIBES_TYPES = {"DESCRIBES"}


def _extract_license(package: dict[str, Any]) -> str | None:
    lic = package.get("licenseConcluded") or package.get("licenseDeclared")
    if lic in (None, "NOASSERTION", "NONE"):
        return None
    return lic


def _extract_repo_url(package: dict[str, Any]) -> str | None:
    for ref in package.get("externalRefs", []):
        if ref.get("referenceCategory") == "PACKAGE-MANAGER" and ref.get("referenceType") == "purl":
            continue  # handled separately as purl, not a repo URL
        if ref.get("referenceType") in ("vcs", "website"):
            return ref.get("referenceLocator")
    return package.get("downloadLocation") if package.get("downloadLocation") not in (
        None, "NOASSERTION", "NONE"
    ) else None


def _extract_purl(package: dict[str, Any]) -> str | None:
    for ref in package.get("externalRefs", []):
        if ref.get("referenceType") == "purl":
            return ref.get("referenceLocator")
    return None


def _extract_ecosystem_from_purl(purl: str | None) -> str | None:
    if not purl or not purl.startswith("pkg:"):
        return None
    return purl[len("pkg:"):].split("/", 1)[0] or None


class SPDXParser(SBOMParser):
    def can_parse(self, raw: dict[str, Any]) -> bool:
        return "spdxVersion" in raw and "packages" in raw

    def parse(self, raw: dict[str, Any]) -> ParsedSBOM:
        if "packages" not in raw:
            raise SBOMParseError("SPDX document is missing required 'packages' array")

        warnings: list[str] = []
        spec_version = raw.get("spdxVersion")

        components: list[ParsedComponent] = []
        for pkg in raw["packages"]:
            ref = pkg.get("SPDXID")
            name = pkg.get("name")
            if not ref or not name:
                warnings.append("Skipped a package missing SPDXID or name")
                continue
            purl = _extract_purl(pkg)
            components.append(
                ParsedComponent(
                    ref=ref,
                    name=name,
                    version=pkg.get("versionInfo"),
                    purl=purl,
                    ecosystem=_extract_ecosystem_from_purl(purl),
                    license=_extract_license(pkg),
                    component_type=ComponentType.LIBRARY,  # SPDX packages don't carry a CDX-style type
                    is_direct=False,  # resolved below once we find the DESCRIBES root
                    source_repo_url=_extract_repo_url(pkg),
                )
            )

        known_refs = {c.ref for c in components}
        root_ref: str | None = None
        direct_refs: set[str] = set()
        edges: list[ParsedDependencyEdge] = []

        for rel in raw.get("relationships", []):
            rel_type = rel.get("relationshipType")
            elem = rel.get("spdxElementId")
            related = rel.get("relatedSpdxElement")
            if not elem or not related:
                continue

            if rel_type in _DESCRIBES_TYPES:
                # The document's root: elem is usually the SPDXRef-DOCUMENT,
                # `related` is the application/package it describes.
                root_ref = related
                continue

            if rel_type in _FORWARD_DEPENDENCY_TYPES:
                source, target = elem, related
            elif rel_type in _REVERSE_DEPENDENCY_TYPES:
                source, target = related, elem
            else:
                warnings.append(f"Unhandled SPDX relationshipType '{rel_type}' — edge skipped")
                continue

            if source not in known_refs or target not in known_refs:
                warnings.append(
                    f"Relationship references unknown package(s): {source} -> {target}"
                )
                continue

            edges.append(ParsedDependencyEdge(source_ref=source, target_ref=target))
            if source == root_ref:
                direct_refs.add(target)

        if root_ref:
            for comp in components:
                if comp.ref in direct_refs:
                    comp.is_direct = True
        else:
            warnings.append(
                "No DESCRIBES relationship found — unable to determine the root application "
                "package; direct-vs-transitive depth will be indeterminate until the "
                "Dependency Graph Engine resolves it."
            )

        return ParsedSBOM(
            format=SBOMFormat.SPDX,
            spec_version=spec_version,
            root_component_ref=root_ref,
            components=components,
            edges=edges,
            warnings=warnings,
        )

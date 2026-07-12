"""
Normalized SBOM schema.

Every parser (CycloneDX, SPDX, future formats) must produce this exact shape.
Downstream modules (Dependency Graph Engine, Risk Analysis Engine, etc.)
depend ONLY on this normalized representation and never touch raw SBOM JSON
directly. This is the seam that lets us add new SBOM formats later without
touching any other module.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SBOMFormat(str, Enum):
    CYCLONEDX = "cyclonedx"
    SPDX = "spdx"


class ComponentType(str, Enum):
    LIBRARY = "library"
    APPLICATION = "application"
    FRAMEWORK = "framework"
    UNKNOWN = "unknown"


class ParsedComponent(BaseModel):
    """A single normalized software component (a library/package version)."""

    # Stable identifier we generate for graph-building purposes.
    # Prefer Package URL (purl) when present since it's the closest thing
    # the ecosystem has to a canonical dependency identifier.
    ref: str = Field(..., description="Unique reference within this SBOM (bom-ref or SPDXID)")
    name: str
    version: Optional[str] = None
    purl: Optional[str] = Field(None, description="Package URL, e.g. pkg:npm/lodash@4.17.15")
    ecosystem: Optional[str] = Field(None, description="npm, pypi, maven, etc., derived from purl")
    license: Optional[str] = Field(None, description="SPDX license expression if declared")
    component_type: ComponentType = ComponentType.UNKNOWN
    is_direct: bool = Field(
        False, description="True if this is a direct dependency of the root application"
    )
    source_repo_url: Optional[str] = Field(
        None, description="VCS URL if declared in the SBOM (external references)"
    )
    last_updated: Optional[str] = Field(
        None, description="ISO date string if the SBOM declares one; often absent and filled in later"
        " by the Repository Intelligence Engine, not this parser"
    )


class ParsedDependencyEdge(BaseModel):
    """A directed edge: `source` depends on `target`."""

    source_ref: str
    target_ref: str


class ParsedSBOM(BaseModel):
    """The full normalized output of any SBOM parser."""

    format: SBOMFormat
    spec_version: Optional[str] = None
    root_component_ref: Optional[str] = Field(
        None, description="The ref of the application/root component itself, if declared"
    )
    components: list[ParsedComponent]
    edges: list[ParsedDependencyEdge]

    # Anything the parser couldn't confidently map — surfaced rather than
    # silently dropped, so Module 3 onward knows the data may be incomplete.
    warnings: list[str] = Field(default_factory=list)

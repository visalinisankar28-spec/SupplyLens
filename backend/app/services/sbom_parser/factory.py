"""
Format-detection factory.

The API layer never imports a specific parser directly — it goes through
`get_parser_for()` so that adding a new SBOM format later (e.g. SWID tags)
is a one-line registration here, not a change anywhere else in the codebase.
"""

from __future__ import annotations

from typing import Any

from app.services.sbom_parser.base import SBOMParseError, SBOMParser
from app.services.sbom_parser.cyclonedx_parser import CycloneDXParser
from app.services.sbom_parser.spdx_parser import SPDXParser

# Order matters only in the pathological case where a document could satisfy
# both can_parse() checks (shouldn't happen in practice — the two formats'
# top-level keys don't overlap — but first-match-wins is the deterministic
# rule if it ever does).
_REGISTERED_PARSERS: list[SBOMParser] = [
    CycloneDXParser(),
    SPDXParser(),
]


def get_parser_for(raw: dict[str, Any]) -> SBOMParser:
    for parser in _REGISTERED_PARSERS:
        if parser.can_parse(raw):
            return parser
    raise SBOMParseError(
        "Unrecognized SBOM format — expected a CycloneDX document "
        "(bomFormat: 'CycloneDX') or an SPDX document (spdxVersion present)."
    )

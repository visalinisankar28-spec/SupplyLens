"""
Parser contract.

Every concrete parser (CycloneDX, SPDX, ...) implements `SBOMParser` and
returns a `ParsedSBOM`. This keeps Module 1 pluggable: adding a new SBOM
format later means writing one new class here, nothing else changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.sbom import ParsedSBOM


class SBOMParseError(Exception):
    """Raised when a document claims to be a format it clearly isn't,
    or is malformed beyond what we can safely recover from."""


class SBOMParser(ABC):
    """Base interface for a single-format SBOM parser."""

    @abstractmethod
    def can_parse(self, raw: dict[str, Any]) -> bool:
        """Cheap structural check — does this raw JSON look like our format?
        Used by the factory to pick a parser before doing the real work."""
        raise NotImplementedError

    @abstractmethod
    def parse(self, raw: dict[str, Any]) -> ParsedSBOM:
        """Parse raw SBOM JSON into the normalized ParsedSBOM shape.

        Must raise SBOMParseError (not a generic exception) on malformed
        input so the API layer can return a clean 422 instead of a 500.
        """
        raise NotImplementedError

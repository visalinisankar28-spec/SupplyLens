import json
from pathlib import Path

import pytest

from app.schemas.sbom import SBOMFormat
from app.services.sbom_parser.base import SBOMParseError
from app.services.sbom_parser.cyclonedx_parser import CycloneDXParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample_cyclonedx.json"


@pytest.fixture
def raw_sbom() -> dict:
    return json.loads(FIXTURE.read_text())


def test_can_parse_detects_cyclonedx(raw_sbom):
    assert CycloneDXParser().can_parse(raw_sbom) is True


def test_parses_all_components(raw_sbom):
    result = CycloneDXParser().parse(raw_sbom)
    assert result.format == SBOMFormat.CYCLONEDX
    assert result.spec_version == "1.5"
    assert len(result.components) == 3
    names = {c.name for c in result.components}
    assert names == {"express", "qs", "leftpad-clone"}


def test_direct_vs_transitive_flagging(raw_sbom):
    result = CycloneDXParser().parse(raw_sbom)
    express = next(c for c in result.components if c.name == "express")
    qs = next(c for c in result.components if c.name == "qs")
    leftpad = next(c for c in result.components if c.name == "leftpad-clone")

    assert express.is_direct is True
    # qs and leftpad-clone are transitive (reached via express -> qs -> leftpad-clone)
    assert qs.is_direct is False
    assert leftpad.is_direct is False


def test_license_extraction(raw_sbom):
    result = CycloneDXParser().parse(raw_sbom)
    leftpad = next(c for c in result.components if c.name == "leftpad-clone")
    assert leftpad.license == "GPL-3.0-only"


def test_ecosystem_derived_from_purl(raw_sbom):
    result = CycloneDXParser().parse(raw_sbom)
    express = next(c for c in result.components if c.name == "express")
    assert express.ecosystem == "npm"


def test_edges_form_expected_chain(raw_sbom):
    result = CycloneDXParser().parse(raw_sbom)
    edge_pairs = {(e.source_ref, e.target_ref) for e in result.edges}
    assert ("pkg:npm/express@4.18.2", "pkg:npm/qs@6.5.2") in edge_pairs
    assert ("pkg:npm/qs@6.5.2", "pkg:npm/leftpad-clone@1.0.0") in edge_pairs


def test_missing_components_key_raises():
    with pytest.raises(SBOMParseError):
        CycloneDXParser().parse({"bomFormat": "CycloneDX", "specVersion": "1.5"})


def test_component_missing_name_is_skipped_not_fatal(raw_sbom):
    raw_sbom["components"].append({"bom-ref": "pkg:npm/mystery@1.0.0", "type": "library"})
    result = CycloneDXParser().parse(raw_sbom)
    assert len(result.components) == 3  # the malformed one was skipped
    assert any("Skipped a component" in w for w in result.warnings)

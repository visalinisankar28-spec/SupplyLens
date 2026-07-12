import json
from pathlib import Path

import pytest

from app.schemas.sbom import SBOMFormat
from app.services.sbom_parser.base import SBOMParseError
from app.services.sbom_parser.spdx_parser import SPDXParser

FIXTURE = Path(__file__).parent / "fixtures" / "sample_spdx.json"


@pytest.fixture
def raw_sbom() -> dict:
    return json.loads(FIXTURE.read_text())


def test_can_parse_detects_spdx(raw_sbom):
    assert SPDXParser().can_parse(raw_sbom) is True


def test_parses_all_packages(raw_sbom):
    result = SPDXParser().parse(raw_sbom)
    assert result.format == SBOMFormat.SPDX
    assert result.spec_version == "SPDX-2.3"
    assert len(result.components) == 3


def test_describes_relationship_sets_root(raw_sbom):
    result = SPDXParser().parse(raw_sbom)
    assert result.root_component_ref == "SPDXRef-Package-checkout-service"


def test_direct_dependency_flagging(raw_sbom):
    result = SPDXParser().parse(raw_sbom)
    flask = next(c for c in result.components if c.name == "flask")
    jinja2 = next(c for c in result.components if c.name == "jinja2")
    assert flask.is_direct is True
    assert jinja2.is_direct is False  # transitive via flask -> jinja2


def test_purl_and_ecosystem_extraction(raw_sbom):
    result = SPDXParser().parse(raw_sbom)
    flask = next(c for c in result.components if c.name == "flask")
    assert flask.purl == "pkg:pypi/flask@2.3.2"
    assert flask.ecosystem == "pypi"


def test_reverse_relationship_type_handled():
    raw = {
        "spdxVersion": "SPDX-2.3",
        "packages": [
            {"SPDXID": "SPDXRef-A", "name": "a"},
            {"SPDXID": "SPDXRef-B", "name": "b"},
        ],
        "relationships": [
            # "B is a DEPENDENCY_OF A" means the edge is A -> B
            {
                "spdxElementId": "SPDXRef-B",
                "relatedSpdxElement": "SPDXRef-A",
                "relationshipType": "DEPENDENCY_OF",
            }
        ],
    }
    result = SPDXParser().parse(raw)
    edge_pairs = {(e.source_ref, e.target_ref) for e in result.edges}
    assert ("SPDXRef-A", "SPDXRef-B") in edge_pairs


def test_missing_packages_key_raises():
    with pytest.raises(SBOMParseError):
        SPDXParser().parse({"spdxVersion": "SPDX-2.3"})


def test_no_describes_relationship_warns_but_does_not_fail():
    raw = {
        "spdxVersion": "SPDX-2.3",
        "packages": [{"SPDXID": "SPDXRef-A", "name": "a"}],
        "relationships": [],
    }
    result = SPDXParser().parse(raw)
    assert result.root_component_ref is None
    assert any("DESCRIBES" in w for w in result.warnings)

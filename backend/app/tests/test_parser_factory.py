import json
from pathlib import Path

import pytest

from app.services.sbom_parser.base import SBOMParseError
from app.services.sbom_parser.cyclonedx_parser import CycloneDXParser
from app.services.sbom_parser.factory import get_parser_for
from app.services.sbom_parser.spdx_parser import SPDXParser

FIXTURES = Path(__file__).parent / "fixtures"


def test_factory_selects_cyclonedx():
    raw = json.loads((FIXTURES / "sample_cyclonedx.json").read_text())
    assert isinstance(get_parser_for(raw), CycloneDXParser)


def test_factory_selects_spdx():
    raw = json.loads((FIXTURES / "sample_spdx.json").read_text())
    assert isinstance(get_parser_for(raw), SPDXParser)


def test_factory_rejects_unknown_format():
    with pytest.raises(SBOMParseError):
        get_parser_for({"someRandomKey": "someRandomValue"})

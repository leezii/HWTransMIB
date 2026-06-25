"""MibParser 测试(封装 PySnmp 7.1)。"""
import pytest

from hwtransmib.kernel.mib_parser import MibParseError, MibParser, ParseResult


@pytest.fixture
def parser(fixtures_mibs_dir):
    return MibParser(extra_sources=[str(fixtures_mibs_dir)])


def test_parse_single_mib(parser):
    result = parser.parse(["IF-MIB"])
    assert isinstance(result, ParseResult)
    assert "IF-MIB" in result.loaded_modules
    assert len(result.errors) == 0


def test_get_oid_by_name(parser):
    parser.parse(["IF-MIB"])
    assert parser.get_oid_by_name("ifDescr") == "1.3.6.1.2.1.2.2.1.2"


def test_get_oid_by_name_module_qualified(parser):
    parser.parse(["IF-MIB"])
    assert parser.get_oid_by_name("ifDescr", "IF-MIB") == "1.3.6.1.2.1.2.2.1.2"


def test_get_oid_before_load_raises(parser):
    with pytest.raises(MibParseError):
        parser.get_oid_by_name("ifDescr")


def test_parse_missing_module_reports_error(parser):
    result = parser.parse(["NONEXISTENT-MIB-XYZ"])
    assert "IF-MIB" not in result.loaded_modules
    assert any("NONEXISTENT-MIB-XYZ" in e for e in result.errors)


def test_is_loaded(parser):
    assert parser.is_loaded("IF-MIB") is False
    parser.parse(["IF-MIB"])
    assert parser.is_loaded("IF-MIB") is True


def test_view_property_raises_before_load(parser):
    with pytest.raises(MibParseError):
        _ = parser.view

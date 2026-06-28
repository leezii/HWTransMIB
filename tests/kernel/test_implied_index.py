"""IMPLIED 索引测试。

SNMP-COMMUNITY-MIB 的 snmpCommunityEntry 用 `INDEX { IMPLIED snmpCommunityIndex }`。
IMPLIED 字符串索引在 OID 编码时省略长度前缀(PySnmp 自动处理)。本测试锁定该行为。
"""
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import NodeType
from hwtransmib.kernel.oid_builder import OidBuilder
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def root(fixtures_mibs_dir):
    parser = MibParser(
        extra_sources=[str(fixtures_mibs_dir),
                       "src/hwtransmib/kernel/standard_mibs"]
    )
    parser.parse(["SNMP-COMMUNITY-MIB"])
    return MibTreeBuilder(parser).build()


def test_implied_flag_captured(root):
    """snmpCommunityEntry 的 index_specs[0].implied == True。"""
    entry = root.find("1.3.6.1.6.3.18.1.1.1")  # snmpCommunityEntry
    assert entry is not None
    assert entry.node_type == NodeType.ROW
    assert entry.index_specs is not None
    assert len(entry.index_specs) == 1
    assert entry.index_specs[0].implied is True
    assert entry.index_specs[0].column_name == "snmpCommunityIndex"


def test_implied_string_oid_no_length_prefix(root, fixtures_mibs_dir):
    """IMPLIED 字符串索引构造无长度前缀。

    snmpCommunityName(列)用 IMPLIED 索引 'public':
    'public' → ASCII 112.117.98.108.105.99(无长度前缀 6)
    """
    parser = MibParser(
        extra_sources=[str(fixtures_mibs_dir),
                       "src/hwtransmib/kernel/standard_mibs"]
    )
    parser.parse(["SNMP-COMMUNITY-MIB"])
    builder = OidBuilder(parser=parser, root=root)
    col = root.find("1.3.6.1.6.3.18.1.1.1.2")  # snmpCommunityName
    assert col is not None
    oid = builder.build(col, {"snmpCommunityIndex": "public"})
    expected_suffix = ".".join(str(ord(c)) for c in "public")
    assert oid == f"1.3.6.1.6.3.18.1.1.1.2.{expected_suffix}"
    # 关键:无长度前缀(非 6.112.117...)
    assert ".6.112." not in oid

"""TC 包装整数类型检测测试(审查 R2 修复)。

锁定缺陷: InetVersion/InterfaceIndex 等 TC 包装的整数类型,syntax 名不含
"INT",旧逻辑靠 isdigit 兜底——数字输入碰巧对,但枚举名(如 ipv4)误放行。

修复: 用 PySnmp syntax 对象基类链判断(IndexSpec.is_integer)。
"""
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import NodeType
from hwtransmib.kernel.oid_builder import OidBuilder, OidBuildError
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def root(fixtures_mibs_dir):
    parser = MibParser(
        extra_sources=[str(fixtures_mibs_dir),
                       "src/hwtransmib/kernel/standard_mibs"]
    )
    parser.parse(["IP-MIB"])
    return MibTreeBuilder(parser).build()


@pytest.fixture
def builder(fixtures_mibs_dir, root):
    parser = MibParser(
        extra_sources=[str(fixtures_mibs_dir),
                       "src/hwtransmib/kernel/standard_mibs"]
    )
    parser.parse(["IP-MIB"])
    return OidBuilder(parser=parser, root=root)


def test_tc_integer_flag_detected(root):
    """TC 包装整数类型(InetVersion)的 index_specs.is_integer == True。"""
    entry = root.find("1.3.6.1.2.1.4.31.3.1")  # ipIfStatsEntry
    assert entry is not None
    assert entry.index_specs is not None
    # 第一列 ipIfStatsIPVersion 是 InetVersion(TC 整数)
    assert entry.index_specs[0].is_integer is True
    # 第二列 ipIfStatsIfIndex 是 InterfaceIndex(TC 整数)
    assert entry.index_specs[1].is_integer is True


def test_tc_integer_accepts_enum_name(builder, root):
    """TC 整数索引输入枚举名(如 'ipv4')现在应通过校验(放开枚举名)。"""
    col = root.find("1.3.6.1.2.1.4.31.3.1.3")  # ipIfStatsInReceives
    errors = builder.validate(col, {
        "ipIfStatsIPVersion": "ipv4",   # 枚举名
        "ipIfStatsIfIndex": "5",
    })
    assert errors == []


def test_tc_integer_accepts_numeric(builder, root):
    """TC 整数索引输入数字应通过校验。"""
    col = root.find("1.3.6.1.2.1.4.31.3.1.3")  # ipIfStatsInReceives
    errors = builder.validate(col, {
        "ipIfStatsIPVersion": "1",   # ipv4
        "ipIfStatsIfIndex": "5",
    })
    assert errors == []


def test_non_integer_tc_not_flagged(root):
    """非整数 TC(IpAddress)的 is_integer == False。"""
    entry = root.find("1.3.6.1.2.1.4.22.1")  # ipNetToMediaEntry
    assert entry is not None
    # 第二列 ipNetToMediaNetAddress 是 IpAddress(非整数)
    addr_spec = next(
        s for s in entry.index_specs
        if s.column_name == "ipNetToMediaNetAddress"
    )
    assert addr_spec.is_integer is False


def test_named_values_extracted_for_enum_tc(root):
    """InetVersion(TC 枚举整数)的 named_values 被提取。"""
    entry = root.find("1.3.6.1.2.1.4.31.3.1")  # ipIfStatsEntry
    spec = entry.index_specs[0]  # ipIfStatsIPVersion = InetVersion
    assert spec.named_values == [("unknown", 0), ("ipv4", 1), ("ipv6", 2)]


def test_named_values_empty_for_non_enum_tc(root):
    """InterfaceIndex(无枚举 TC 整数)的 named_values 为空列表。"""
    entry = root.find("1.3.6.1.2.1.4.31.3.1")  # ipIfStatsEntry
    spec = entry.index_specs[1]  # ipIfStatsIfIndex = InterfaceIndex
    assert spec.named_values == []

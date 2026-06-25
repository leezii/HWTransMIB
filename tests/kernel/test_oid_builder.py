"""OidBuilder 测试:标量与表列 OID 构造(核心)。

基于探测: getInstIdFromIndices(5) 返回 (5,),仅索引后缀。
拼接规则: column OID + "." + 索引后缀。
"""
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import NodeType
from hwtransmib.kernel.oid_builder import OidBuildError, OidBuilder
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def builder(fixtures_mibs_dir):
    parser = MibParser(extra_sources=[str(fixtures_mibs_dir)])
    parser.parse(["IF-MIB"])
    root = MibTreeBuilder(parser).build()
    return OidBuilder(parser=parser, root=root)


@pytest.fixture
def ip_builder(fixtures_mibs_dir):
    """IP-MIB 构造器,含多列索引(Integer32 + IpAddress)表。"""
    parser = MibParser(extra_sources=[str(fixtures_mibs_dir)])
    parser.parse(["IP-MIB"])
    root = MibTreeBuilder(parser).build()
    return OidBuilder(parser=parser, root=root)


def _find(root, oid):
    node = root.find(oid)
    assert node is not None, f"未找到节点 {oid}"
    return node


def test_scalar_appends_zero(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.1")  # ifNumber 标量
    assert node.node_type == NodeType.SCALAR
    result = builder.build(node, {})
    assert result == "1.3.6.1.2.1.2.1.0"


def test_column_single_integer_index(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")  # ifDescr COLUMN
    result = builder.build(node, {"ifIndex": "5"})
    assert result == "1.3.6.1.2.1.2.2.1.2.5"


def test_column_requires_index(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    with pytest.raises(OidBuildError):
        builder.build(node, {})


def test_column_non_integer_rejected(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    with pytest.raises(OidBuildError):
        builder.build(node, {"ifIndex": "abc"})


def test_non_constructible_node_raises(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2")  # ifTable TABLE
    with pytest.raises(OidBuildError):
        builder.build(node, {})


def test_validate_returns_errors(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    errors = builder.validate(node, {"ifIndex": "abc"})
    assert any("ifIndex" in e for e in errors)


def test_validate_ok(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    errors = builder.validate(node, {"ifIndex": "5"})
    assert errors == []


def test_validate_non_constructible(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2")  # TABLE
    errors = builder.validate(node, {})
    assert any("不可构造" in e for e in errors)


def test_validate_empty_index(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    errors = builder.validate(node, {"ifIndex": ""})
    assert any("未填写" in e for e in errors)


# --- 多列索引 + TC 包装类型(R1 回归) ---

def test_multi_column_index_integer_and_ip(ip_builder):
    """ipNetToMediaPhysAddress: INDEX {Integer32, IpAddress}。
    规格场景 C:多列索引,IP 编码为点分四段。
    """
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.22.1.2")  # ipNetToMediaPhysAddress
    result = ip_builder.build(node, {
        "ipNetToMediaIfIndex": "1",
        "ipNetToMediaNetAddress": "192.168.1.1",
    })
    # Integer32=1, IpAddress 192.168.1.1 → 编码为 1.192.168.1.1
    assert result == "1.3.6.1.2.1.4.22.1.2.1.192.168.1.1"


def test_multi_column_requires_all_indices(ip_builder):
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.22.1.2")
    errors = ip_builder.validate(node, {"ipNetToMediaIfIndex": "1"})
    # 第二列 ipNetToMediaNetAddress 未填写
    assert any("ipNetToMediaNetAddress" in e for e in errors)


def test_tc_wrapped_integer_does_not_crash(ip_builder):
    """R1 回归:TC 包装的整数索引(Integer32)输入非法值不崩溃。"""
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.22.1.2")
    # 校验应捕获非法整数(而非让 PyAsn1Error 冒泡崩溃)
    errors = ip_builder.validate(node, {
        "ipNetToMediaIfIndex": "abc",
        "ipNetToMediaNetAddress": "192.168.1.1",
    })
    assert any("需要整数" in e for e in errors)


def test_tc_wrapped_integer_build_returns_error(ip_builder):
    """R1 回归:即使绕过校验,build 也转为 OidBuildError 而非崩溃。"""
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.22.1.2")
    import pytest
    with pytest.raises(OidBuildError):
        ip_builder.build(node, {
            "ipNetToMediaIfIndex": "99999999999999999999",  # 溢出整数
            "ipNetToMediaNetAddress": "192.168.1.1",
        })

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

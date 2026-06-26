"""MibTreeBuilder 测试:从 PySnmp 产物构建 MibNode 树。"""
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def root(fixtures_mibs_dir):
    parser = MibParser(extra_sources=[str(fixtures_mibs_dir)])
    parser.parse(["IF-MIB"])
    return MibTreeBuilder(parser).build()


def test_build_returns_root(root: MibNode):
    # 根是 iso (1)
    assert root.oid == "1"
    assert root.name == "iso"


def test_find_node_by_oid(root: MibNode):
    node = root.find("1.3.6.1.2.1.2.2.1.2")
    assert node is not None
    assert node.name == "ifDescr"
    assert node.node_type == NodeType.COLUMN


def test_if_table_is_table_type(root: MibNode):
    node = root.find("1.3.6.1.2.1.2.2")
    assert node is not None
    assert node.node_type == NodeType.TABLE


def test_if_entry_is_row_type(root: MibNode):
    node = root.find("1.3.6.1.2.1.2.2.1")
    assert node is not None
    assert node.node_type == NodeType.ROW


def test_if_entry_has_index_specs(root: MibNode):
    entry = root.find("1.3.6.1.2.1.2.2.1")
    assert entry is not None
    assert entry.index_specs is not None
    assert len(entry.index_specs) == 1
    assert entry.index_specs[0].column_name == "ifIndex"


def test_index_spec_has_oid(root: MibNode):
    entry = root.find("1.3.6.1.2.1.2.2.1")
    spec = entry.index_specs[0]
    assert spec.column_oid == "1.3.6.1.2.1.2.2.1.1"


def test_scalar_node_type(root: MibNode):
    node = root.find("1.3.6.1.2.1.2.1")  # ifNumber 标量
    assert node is not None
    assert node.node_type == NodeType.SCALAR


def test_node_has_attributes(root: MibNode):
    node = root.find("1.3.6.1.2.1.2.2.1.2")  # ifDescr
    assert node is not None
    assert node.module_name == "IF-MIB"
    # access 应是 read-only 或 read-write(非空)
    assert node.access is not None


def test_find_nonexistent_returns_none(root: MibNode):
    assert root.find("9.9.9.9") is None

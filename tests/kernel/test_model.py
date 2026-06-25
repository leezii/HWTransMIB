"""MibNode / NodeType / IndexSpec 领域模型测试。"""
from hwtransmib.kernel.model import IndexSpec, MibNode, NodeType


def test_node_type_values():
    assert NodeType.SCALAR.value == "scalar"
    assert NodeType.COLUMN.value == "column"
    assert NodeType.TABLE.value == "table"
    assert NodeType.ROW.value == "row"


def test_is_constructible_scalar():
    node = MibNode(oid="1.3.6.1.2.1.1.1", name="sysDescr", node_type=NodeType.SCALAR)
    assert node.is_constructible is True


def test_is_constructible_column():
    node = MibNode(oid="1.3.6.1.2.1.2.2.1.2", name="ifDescr", node_type=NodeType.COLUMN)
    assert node.is_constructible is True


def test_not_constructible_table():
    node = MibNode(oid="1.3.6.1.2.1.2.2", name="ifTable", node_type=NodeType.TABLE)
    assert node.is_constructible is False


def test_child_relationship():
    root = MibNode(oid="1.3", name="org", node_type=NodeType.SUBTREE)
    child = MibNode(oid="1.3.6", name="dod", node_type=NodeType.SUBTREE, parent=root)
    root.children.append(child)
    assert child.parent is root
    assert root.children == [child]


def test_name_path():
    root = MibNode(oid="1.3.6.1.2.1.2.2.1", name="ifEntry", node_type=NodeType.ROW)
    leaf = MibNode(oid="1.3.6.1.2.1.2.2.1.2", name="ifDescr",
                   node_type=NodeType.COLUMN, parent=root)
    root.children.append(leaf)
    assert leaf.name_path == ["ifEntry", "ifDescr"]


def test_index_spec_defaults():
    spec = IndexSpec(column_name="ifIndex", column_oid="1.3.6.1.2.1.2.2.1.1",
                     implied=False, syntax="INTEGER")
    assert spec.implied is False
    assert spec.syntax == "INTEGER"


def test_find_by_oid():
    root = MibNode(oid="1.3", name="org", node_type=NodeType.SUBTREE)
    mid = MibNode(oid="1.3.6", name="dod", node_type=NodeType.SUBTREE, parent=root)
    leaf = MibNode(oid="1.3.6.1", name="internet", node_type=NodeType.SUBTREE, parent=mid)
    root.children.append(mid)
    mid.children.append(leaf)
    assert root.find("1.3.6.1") is leaf
    assert root.find("1.3.6") is mid
    assert root.find("1.3.6.1") is leaf
    assert root.find("9.9.9") is None

"""MibTreeModel 测试:QAbstractItemModel 两列(名称+OID)。"""
from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.ui.mib_tree_model import MibTreeModel


def _tree() -> MibNode:
    root = MibNode("1", "iso", NodeType.SUBTREE)
    a = MibNode("1.3", "org", NodeType.SUBTREE, parent=root)
    b = MibNode("1.3.6", "dod", NodeType.SUBTREE, parent=a)
    leaf = MibNode("1.3.6.1.2.1.1.1", "sysDescr", NodeType.SCALAR, parent=b)
    root.children = [a]
    a.children = [b]
    b.children = [leaf]
    return root


def test_column_count():
    model = MibTreeModel(_tree())
    assert model.columnCount() == 2  # 名称 + OID


def test_root_index_name():
    from PySide6.QtCore import Qt
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    assert "iso" in root_idx.data(Qt.ItemDataRole.DisplayRole)


def test_oid_column_data():
    from PySide6.QtCore import Qt
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    child_idx = model.index(0, 0, root_idx)  # org
    oid_idx = model.index(0, 1, root_idx)
    assert oid_idx.data(Qt.ItemDataRole.DisplayRole) == "1.3"


def test_row_count():
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    assert model.rowCount(root_idx) == 1  # org


def test_node_from_index():
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    node = model.node_from_index(root_idx)
    assert node.name == "iso"


def test_user_role_returns_node():
    from PySide6.QtCore import Qt
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    node = root_idx.data(Qt.ItemDataRole.UserRole)
    assert node.name == "iso"


def test_parent_relationship():
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    child_idx = model.index(0, 0, root_idx)  # org
    parent_idx = model.parent(child_idx)
    assert parent_idx == root_idx


def test_reset_root():
    model = MibTreeModel(_tree())
    new_root = _tree()
    model.reset_root(new_root)  # 不应抛异常
    assert model.columnCount() == 2

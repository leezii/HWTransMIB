"""MIB 树的 QAbstractItemModel 实现。

两列:名称(带图标)、OID。树按 OID 层级组织。
用一个不可见根包装真实根,使顶层只显示 iso(1)。
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from hwtransmib.kernel.model import MibNode, NodeType

# 节点类型 → 图标(Emoji,跨平台)
_ICON = {
    NodeType.MODULE: "📦",
    NodeType.SUBTREE: "📁",
    NodeType.SCALAR: "🟢",
    NodeType.TABLE: "🔴",
    NodeType.ROW: "🔴",
    NodeType.COLUMN: "🟢",
}


class MibTreeModel(QAbstractItemModel):
    """两列:节点名称(带图标)、OID。"""

    def __init__(self, root: MibNode) -> None:
        super().__init__()
        # 不可见根,使顶层只有一个节点
        self._invisible = MibNode(oid="", name="", node_type=NodeType.SUBTREE)
        self._invisible.children = [root]
        root.parent = self._invisible

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = self._node_from_index(parent)
        if row < 0 or row >= len(parent_node.children):
            return QModelIndex()
        child = parent_node.children[row]
        return self.createIndex(row, column, child)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = self._node_from_index(index)
        parent = node.parent
        if parent is None or parent is self._invisible:
            return QModelIndex()
        grand = parent.parent or self._invisible
        if grand is self._invisible:
            row = 0
        else:
            row = grand.children.index(parent)
        return self.createIndex(row, 0, parent)

    def rowCount(self, parent=QModelIndex()):
        return len(self._node_from_index(parent).children)

    def columnCount(self, parent=QModelIndex()):
        return 2

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node = self._node_from_index(index)
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                icon = _ICON.get(node.node_type, "")
                return f"{icon} {node.name}" if icon else node.name
            return node.oid
        if role == Qt.ItemDataRole.UserRole:
            return node
        return None

    def headerData(self, section, orientation,
                   role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and \
                orientation == Qt.Orientation.Horizontal:
            return ["节点", "OID"][section]
        return None

    def _node_from_index(self, index) -> MibNode:
        if index.isValid():
            return index.internalPointer()
        return self._invisible

    def node_from_index(self, index) -> MibNode:
        """公开方法:UI 通过 index 取 MibNode。"""
        return self._node_from_index(index)

    def index_from_oid(self, oid: str) -> QModelIndex:
        """按完整 OID 查找对应的 QModelIndex(用于搜索跳转/收藏定位)。

        沿父链递归构造 index。找不到返回空 index。
        """
        node = self._invisible.children[0].find(oid) if self._invisible.children else None
        if node is None:
            return QModelIndex()
        return self._index_of_node(node)

    def _index_of_node(self, node: MibNode) -> QModelIndex:
        """递归构造指向 node 的 QModelIndex。"""
        if node.parent is None or node.parent is self._invisible:
            return self.index(0, 0)
        parent_idx = self._index_of_node(node.parent)
        # 在父的 children 中找本节点的行号
        row = node.parent.children.index(node)
        return self.index(row, 0, parent_idx)

    def reset_root(self, root: MibNode) -> None:
        """重新导入后替换整棵树。"""
        self.beginResetModel()
        self._invisible.children = [root]
        root.parent = self._invisible
        self.endResetModel()

"""持久化展开状态的 QTreeView 子类。

QTreeView 的视图项(view items)是懒创建的:setExpanded 在子项尚未实例化时
只设置内部标志,视觉上不渲染(需点击/滚动才触发)。标准 setExpanded 恢复
在大树上因此失效。

解决方案:重写 rowsInserted——每当模型的行被插入(即 view item 创建)时,
检查该节点是否应展开,若是则展开。这与视图项创建时机绑定,确定性生效。
"""
from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QTreeView


class PersistentTreeView(QTreeView):
    """在行插入时自动应用记录的展开状态。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # 记录"应展开"的节点 OID 集合
        self._expanded_oids: set[str] = set()

    def set_expanded_oids(self, oids: set[str]) -> None:
        """设置应展开的节点 OID 集合,并对当前模型立即应用。

        自顶向下逐层 setExpanded,并对每个节点 scrollTo 强制 Qt 创建并
        渲染该节点的 view item。setExpanded 对未实例化的 item 只设标志,
        scrollTo 才是强制渲染的标准方法。
        """
        self._expanded_oids = set(oids)
        model = self.model()
        if model is None:
            return
        # 按 OID 深度排序(父先于子),逐个展开 + scrollTo 强制渲染
        for oid in sorted(self._expanded_oids):
            idx = self._find_index_by_oid(model, oid)
            if idx.isValid():
                self.setExpanded(idx, True)
                self.scrollTo(idx)

    def _find_index_by_oid(self, model, oid: str) -> QModelIndex:
        """在模型中按 OID 查找 QModelIndex。

        模型若有 index_from_oid 方法(MibTreeModel)则用它;否则遍历。
        """
        if hasattr(model, "index_from_oid"):
            return model.index_from_oid(oid)
        return QModelIndex()

    def expanded_oids(self) -> set[str]:
        return set(self._expanded_oids)

    def add_expanded(self, oid: str) -> None:
        self._expanded_oids.add(oid)

    def remove_expanded(self, oid: str) -> None:
        self._expanded_oids.discard(oid)

    def rowsInserted(self, parent: QModelIndex, start: int, end: int) -> None:
        """行插入时(视图项创建),自动展开应展开的节点。

        这是确定性渲染的关键:setExpanded 展开父节点会创建子项,
        触发本方法;在此检查新创建的子项是否也应展开,递归实例化。
        """
        super().rowsInserted(parent, start, end)
        model = self.model()
        if model is None:
            return
        for row in range(start, end + 1):
            child = model.index(row, 0, parent)
            if not child.isValid():
                continue
            oid = child.data(Qt.ItemDataRole.UserRole)
            if oid and oid in self._expanded_oids:
                self.setExpanded(child, True)

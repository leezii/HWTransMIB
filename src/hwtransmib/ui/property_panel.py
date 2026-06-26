"""节点属性面板:键值对表格展示 MibNode 元数据。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from hwtransmib.kernel.model import MibNode, NodeType

_NO_EDIT = ~Qt.ItemFlag.ItemIsEditable


class PropertyPanel(QWidget):
    """以两列表格(属性 / 值)展示节点元数据。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self._title = QLabel("属性")
        layout.addWidget(self._title)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["属性", "值"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

    def show_node(self, node: MibNode) -> None:
        """填充属性表格,含索引构成(ROW/TABLE 节点)。"""
        rows = [
            ("名称", node.name),
            ("完整 OID", node.oid),
            ("类型", node.node_type.value),
            ("SYNTAX", node.syntax or "—"),
            ("MAX-ACCESS", node.access or "—"),
            ("STATUS", node.status or "—"),
            ("UNITS", node.units or "—"),
            ("所属模块", node.module_name or "—"),
            ("可构造 OID", "是" if node.is_constructible else "否"),
            ("DESCRIPTION", node.description or "—"),
        ]

        # 追加索引构成(ROW 直接取,TABLE 取子 ROW)
        index_specs, source_row = self._resolve_index_specs(node)
        if source_row is not None and source_row is not node:
            # TABLE 取子 ROW:标注来源
            rows.append((f"索引构成(来自 {source_row.name})", ""))
        if index_specs:
            for i, spec in enumerate(index_specs, start=1):
                value = f"{spec.column_name} ({spec.column_oid}) · {spec.syntax}"
                if spec.implied:
                    value += " · IMPLIED"
                rows.append((f"索引列 {i}", value))
        elif source_row is not None:
            rows.append(("索引构成", "无"))

        self._title.setText(f"属性 — {node.name}")
        self._table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            key_item = QTableWidgetItem(k)
            key_item.setFlags(key_item.flags() & _NO_EDIT)
            val_item = QTableWidgetItem(str(v))
            val_item.setFlags(val_item.flags() & _NO_EDIT)
            self._table.setItem(r, 0, key_item)
            self._table.setItem(r, 1, val_item)
        self._table.resizeRowsToContents()

    def _resolve_index_specs(self, node: MibNode):
        """返回 (index_specs, source_row)。

        ROW:直接用 node.index_specs,source_row=node。
        TABLE:取第一个 ROW 子节点的 index_specs,source_row=该子节点。
        其他:返回 (None, None)。
        """
        if node.node_type == NodeType.ROW:
            return node.index_specs, node
        if node.node_type == NodeType.TABLE:
            for child in node.children:
                if child.node_type == NodeType.ROW and child.index_specs is not None:
                    return child.index_specs, child
            return None, node  # TABLE 但无 ROW 子节点
        return None, None

"""节点属性面板:键值对表格展示 MibNode 元数据。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from hwtransmib.kernel.model import MibNode

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
        """填充属性表格。"""
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

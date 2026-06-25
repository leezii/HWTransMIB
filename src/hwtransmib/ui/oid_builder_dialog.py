"""OID 构造对话框:根据节点类型展示表单,实时预览结果。

标量: 显示 .0 结果,无输入项。
表列(COLUMN): 按 INDEX 定义展示索引输入框,实时拼接预览。
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.kernel.oid_builder import OidBuildError
from hwtransmib.services.oid_build_service import OidBuildService


class OidBuilderDialog(QDialog):
    """OID 构造对话框。"""

    def __init__(self, node: MibNode, service: OidBuildService,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._node = node
        self._service = service
        self._inputs: dict[str, QLineEdit] = {}
        self.setWindowTitle(f"构造 OID — {node.name}")
        self.setMinimumWidth(420)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        info = QLabel(
            f"节点:<b>{self._node.name}</b>  基础 OID:{self._node.oid}"
        )
        layout.addWidget(info)

        specs = self._row_specs()
        if specs:
            form = QFormLayout()
            for spec in specs:
                edit = QLineEdit()
                edit.setPlaceholderText(spec.syntax)
                edit.textChanged.connect(self._refresh)
                self._inputs[spec.column_name] = edit
                form.addRow(f"{spec.column_name} ({spec.syntax})", edit)
            layout.addLayout(form)
        elif self._node.node_type == NodeType.SCALAR:
            layout.addWidget(QLabel("标量节点,自动追加 .0 实例后缀"))

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(60)
        layout.addWidget(self._preview)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("📋 复制 OID")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)
        cancel_btn = QPushButton("关闭")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _row_specs(self):
        """沿父链查找所属 ROW 的 index_specs。"""
        parent = self._node.parent
        while parent is not None:
            if parent.index_specs:
                return parent.index_specs
            parent = parent.parent
        return []

    def set_index_value(self, column_name: str, value: str) -> None:
        """测试/外部设置索引值。"""
        edit = self._inputs.get(column_name)
        if edit is not None:
            edit.setText(value)

    def result_text(self) -> str:
        """返回当前预览文本。"""
        return self._preview.toPlainText().strip()

    def _values(self) -> dict[str, str]:
        return {name: e.text() for name, e in self._inputs.items()}

    def _refresh(self) -> None:
        """输入变化时实时重算预览。"""
        values = self._values()
        errors = self._service.validate(self._node, values)
        if errors:
            self._preview.setPlainText("⚠ " + "; ".join(errors))
            return
        try:
            oid = self._service.build(self._node, values)
            self._preview.setPlainText(oid)
        except OidBuildError as exc:
            self._preview.setPlainText("⚠ " + str(exc))

    def _copy(self) -> None:
        """复制 OID 到剪贴板,并记录历史。"""
        errors = self._service.validate(self._node, self._values())
        if errors:
            QMessageBox.warning(self, "无法复制", "; ".join(errors))
            return
        oid = self._service.build_and_record(self._node, self._values())
        QApplication.clipboard().setText(oid)
        QMessageBox.information(self, "已复制", oid)

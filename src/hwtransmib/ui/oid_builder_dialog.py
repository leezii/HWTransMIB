"""OID 构造对话框:根据节点类型展示表单,实时预览结果。

标量: 显示 .0 结果,无输入项。
表列(COLUMN): 按 INDEX 定义展示索引输入框,实时拼接预览。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCompleter, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.kernel.oid_builder import OidBuildError
from hwtransmib.kernel.string_templates import StringTemplateStore
from hwtransmib.services.oid_build_service import OidBuildService


class OidBuilderDialog(QDialog):
    """OID 构造对话框。"""

    def __init__(self, node: MibNode, service: OidBuildService,
                 templates: StringTemplateStore | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._node = node
        self._service = service
        self._templates = templates
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
                self._attach_completer(edit, spec)
                self._prefill_template(spec, edit)
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

    def _attach_completer(self, edit: QLineEdit, spec) -> None:
        """对带枚举的索引列挂补全器:键入少量字符匹配枚举名。"""
        if not spec.named_values:
            return
        labels = [f"{name} ({value})" for name, value in spec.named_values]
        completer = QCompleter(labels, edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        edit.setCompleter(completer)

    def _prefill_template(self, spec, edit: QLineEdit) -> None:
        """字符串类索引列(非整数、非枚举)查模板预填;命中则 setText。

        预填用 setText 会触发 textChanged → _refresh,对话框打开即显示
        编码后的 OID 预览。仅在 _build_ui 构造时执行一次,之后不覆盖用户编辑。
        """
        if self._templates is None:
            return
        # 仅字符串类列查模板:非整数、非枚举
        if spec.is_integer or spec.named_values:
            return
        if not spec.column_oid:
            return
        template = self._templates.lookup(spec.column_oid)
        if template:
            # 构造期间 _preview 尚未创建,屏蔽信号避免 textChanged → _refresh
            # 触碰未就绪的属性;__init__ 末尾的 _refresh() 会算出正确预览。
            edit.blockSignals(True)
            edit.setText(template)
            edit.blockSignals(False)

    def set_index_value(self, column_name: str, value: str) -> None:
        """测试/外部设置索引值。"""
        edit = self._inputs.get(column_name)
        if edit is not None:
            edit.setText(value)

    def result_text(self) -> str:
        """返回当前预览文本。"""
        return self._preview.toPlainText().strip()

    def _values(self) -> dict[str, str]:
        return {name: self._normalize(name, e.text())
                for name, e in self._inputs.items()}

    def _normalize(self, column_name: str, text: str) -> str:
        """规范化输入值。

        仅对带枚举的列生效:选中下拉项形如 'name (n)' 时取枚举名,
        交内核编码;纯数字/裸枚举名原样返回。其余列直接返回 text。
        """
        spec = self._spec_of(column_name)
        if spec is None or not spec.named_values:
            return text
        text = text.strip()
        # 形如 "name (n)" → 取括号前的枚举名
        idx = text.rfind(" (")
        if idx > 0 and text.endswith(")"):
            candidate = text[:idx]
            if any(candidate == n for n, _ in spec.named_values):
                return candidate
        return text

    def _spec_of(self, column_name: str):
        """按列名查 IndexSpec(从所属 ROW 的 index_specs)。"""
        for spec in self._row_specs():
            if spec.column_name == column_name:
                return spec
        return None

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

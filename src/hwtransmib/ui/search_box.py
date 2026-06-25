"""搜索框:输入停止 200ms 后触发搜索信号。

防抖用 QTimer 实现,避免大 MIB 库下每次按键都搜索导致卡顿。
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLineEdit


class SearchBox(QLineEdit):
    """带防抖的搜索输入框。"""

    search_requested = Signal(str)

    def __init__(self, parent=None, debounce_ms: int = 200) -> None:
        super().__init__(parent)
        self.setPlaceholderText("🔍 搜索 节点名称 / OID...")
        self.setClearButtonEnabled(True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._emit)
        self.textChanged.connect(self._schedule)

    def _schedule(self) -> None:
        """文本变化时重置防抖计时。"""
        self._timer.start()

    def _emit(self) -> None:
        """防抖结束后发出搜索信号。"""
        self.search_requested.emit(self.text().strip())

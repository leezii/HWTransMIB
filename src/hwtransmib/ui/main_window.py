"""主窗口:MIB 树(上) + 可折叠详情区(下,含属性面板与收藏/历史 Tab)。

布局(规格第 2 节):
- 顶部工具栏:导入按钮 + 搜索框 + 详情切换按钮
- 上下 QSplitter:上半 = MIB 树(占多数空间),下半 = 详情区
- 详情区:左 = 属性面板,右 = 收藏/历史 Tab
- 详情区默认可由工具栏按钮切换显隐,双击树节点自动展开
- 状态栏:加载 MIB 数、节点数、就绪状态
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QClipboard
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem,
    QTabWidget, QTreeView, QVBoxLayout, QWidget,
)

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportReport, ImportService
from hwtransmib.services.oid_build_service import OidBuildService
from hwtransmib.services.search_service import SearchService
from hwtransmib.ui.mib_tree_model import MibTreeModel
from hwtransmib.ui.oid_builder_dialog import OidBuilderDialog
from hwtransmib.ui.property_panel import PropertyPanel
from hwtransmib.ui.search_box import SearchBox


class MainWindow(QMainWindow):
    """主窗口。"""

    def __init__(self, import_service: ImportService,
                 user_data: UserData) -> None:
        super().__init__()
        self.setWindowTitle("🌲 HWTransMIB")
        self.resize(1000, 700)
        self._import = import_service
        self._ud = user_data
        self._oid_svc: OidBuildService | None = None
        self._search_svc: SearchService | None = None
        self._model: MibTreeModel | None = None

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)

        # 顶部工具栏
        toolbar = QHBoxLayout()
        self._import_btn = QPushButton("📂 导入 MIB")
        self._import_btn.clicked.connect(self._on_import)
        self._search = SearchBox()
        self._search.search_requested.connect(self._on_search)
        self._detail_btn = QPushButton("📋 详情")
        self._detail_btn.setCheckable(True)
        self._detail_btn.toggled.connect(self._toggle_detail)
        toolbar.addWidget(self._import_btn)
        toolbar.addWidget(self._search, 1)
        toolbar.addWidget(self._detail_btn)
        outer.addLayout(toolbar)

        # 上下分割:树 + 详情
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._tree = QTreeView()
        self._tree.setUniformRowHeights(True)
        self._tree.setHeaderHidden(False)
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        self._tree.clicked.connect(self._on_select_node)
        self._tree.doubleClicked.connect(self._on_activate_node)
        self._splitter.addWidget(self._tree)

        self._detail = self._build_detail()
        self._splitter.addWidget(self._detail)
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 1)
        outer.addWidget(self._splitter, 1)

        # 状态栏
        self._status = QLabel("就绪 — 点击「导入 MIB」开始")
        self.statusBar().addWidget(self._status)

        # 应用持久化的显隐状态 + 窗口几何 + 分割比例
        cfg = self._ud.config()
        self._detail_btn.setChecked(cfg.get("detail_visible", True))
        if cfg.get("window_geometry"):
            import base64
            self.restoreGeometry(
                base64.b64decode(cfg["window_geometry"])
            )
        if cfg.get("split_sizes"):
            self._splitter.setSizes(cfg["split_sizes"])
        # 启动自动重载上次导入的 MIB(规格第 7 节)
        self._auto_reload_imports()
        self._refresh_favorites()
        self._refresh_history()

    def _auto_reload_imports(self) -> None:
        """启动时自动重新导入上次记录的 MIB 文件。"""
        files = self._ud.imports().get("files", [])
        if not files:
            return
        existing = [f for f in files if Path(f).exists()]
        if not existing:
            return
        report = self._import.import_files(existing)
        if report.loaded_modules:
            root = self._import.get_root()
            self._model = MibTreeModel(root)
            self._tree.setModel(self._model)
            self._tree.expandToDepth(1)
            self._oid_svc = OidBuildService(
                parser=self._import.get_parser(), root=root,
                user_data=self._ud,
            )
            self._search_svc = SearchService(root=root)
            self._status.setText(
                f"已重载 {len(report.loaded_modules)} 个 MIB · "
                f"{report.node_count} 节点"
            )

    def _build_detail(self) -> QWidget:
        """构建详情区:左属性面板 + 右收藏/历史 Tab。"""
        box = QGroupBox("详情")
        layout = QHBoxLayout(box)
        layout.setContentsMargins(4, 4, 4, 4)
        self._property = PropertyPanel()
        layout.addWidget(self._property, 3)
        self._tabs = QTabWidget()
        self._fav_view = QTableWidget(0, 2)
        self._fav_view.setHorizontalHeaderLabels(["节点", "OID"])
        self._fav_view.verticalHeader().setVisible(False)
        self._hist_view = QTableWidget(0, 2)
        self._hist_view.setHorizontalHeaderLabels(["OID", "节点"])
        self._hist_view.verticalHeader().setVisible(False)
        self._tabs.addTab(self._fav_view, "★ 收藏")
        self._tabs.addTab(self._hist_view, "🕑 历史")
        layout.addWidget(self._tabs, 2)
        return box

    def _toggle_detail(self, visible: bool) -> None:
        self._detail.setVisible(visible)

    def _on_import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 MIB 文件", "",
            "MIB 文件 (*.mib *.txt *.my);;所有文件 (*)",
        )
        if not paths:
            return
        report: ImportReport = self._import.import_files(paths)
        if not report.loaded_modules:
            QMessageBox.warning(
                self, "导入失败", "无模块成功加载:\n" + "\n".join(report.errors)
            )
            return
        root = self._import.get_root()
        self._model = MibTreeModel(root)
        self._tree.setModel(self._model)
        self._tree.expandToDepth(1)
        self._oid_svc = OidBuildService(
            parser=self._import.get_parser(), root=root, user_data=self._ud
        )
        self._search_svc = SearchService(root=root)
        self._ud.set_imports(paths)
        self._refresh_favorites()
        self._refresh_history()
        self._status.setText(
            f"已加载 {len(report.loaded_modules)} 个 MIB · "
            f"{report.node_count} 节点"
        )
        if report.errors:
            QMessageBox.warning(
                self, "部分导入失败", "\n".join(report.errors)
            )

    def _current_node(self) -> MibNode | None:
        idx = self._tree.currentIndex()
        if self._model is None or not idx.isValid():
            return None
        return self._model.node_from_index(idx)

    def _on_select_node(self) -> None:
        """单击节点:更新属性面板。"""
        node = self._current_node()
        if node:
            self._property.show_node(node)

    def _on_activate_node(self) -> None:
        """双击节点:展开详情区,若可构造则打开构造对话框。"""
        if not self._detail_btn.isChecked():
            self._detail_btn.setChecked(True)
        node = self._current_node()
        if node:
            self._property.show_node(node)
            if node.is_constructible:
                self._open_builder(node)

    def _on_search(self, query: str) -> None:
        if self._search_svc is None or not query:
            return
        results = self._search_svc.search(query)
        if results:
            self._select_node(results[0])

    def _select_node(self, node: MibNode) -> None:
        """搜索/收藏定位:在树中展开并选中节点,更新属性面板。"""
        self._property.show_node(node)
        if self._model is not None:
            idx = self._model.index_from_oid(node.oid)
            if idx.isValid():
                self._tree.setCurrentIndex(idx)
                self._tree.scrollTo(idx)
                # 展开所有祖先
                parent = idx.parent()
                while parent.isValid():
                    self._tree.setExpanded(parent, True)
                    parent = parent.parent()

    def _open_builder(self, node: MibNode) -> None:
        if self._oid_svc is None:
            return
        dlg = OidBuilderDialog(node, self._oid_svc, self)
        dlg.exec()
        # 对话框关闭后刷新历史(复制操作可能已记录)
        self._refresh_history()

    def _on_context_menu(self, pos) -> None:
        """树节点右键菜单:构造 OID / 复制 OID / 收藏 / 复制名称。"""
        idx = self._tree.indexAt(pos)
        if not idx.isValid():
            return
        self._tree.setCurrentIndex(idx)
        node = self._model.node_from_index(idx) if self._model else None
        if node is None:
            return
        menu = QMenu(self)

        # 构造 OID(仅可构造节点)
        build_action = QAction("🔧 构造 OID", self)
        build_action.triggered.connect(lambda: self._open_builder(node))
        build_action.setEnabled(node.is_constructible)
        menu.addAction(build_action)

        # 复制 OID
        copy_oid_action = QAction("📋 复制 OID", self)
        copy_oid_action.triggered.connect(
            lambda: self._copy_text(node.oid)
        )
        menu.addAction(copy_oid_action)

        # 复制名称
        copy_name_action = QAction("📝 复制名称", self)
        copy_name_action.triggered.connect(
            lambda: self._copy_text(node.name)
        )
        menu.addAction(copy_name_action)

        menu.addSeparator()

        # 收藏(切换)
        is_fav = any(i.get("oid") == node.oid
                     for i in self._ud.favorites()["items"])
        fav_action = QAction(
            "✕ 取消收藏" if is_fav else "★ 收藏", self
        )
        fav_action.triggered.connect(lambda: self._toggle_favorite(node))
        menu.addAction(fav_action)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _copy_text(self, text: str) -> None:
        """复制文本到剪贴板。"""
        QApplication.clipboard().setText(text)
        self._status.setText(f"已复制: {text}")

    def _toggle_favorite(self, node: MibNode) -> None:
        """添加或移除收藏。"""
        items = self._ud.favorites()["items"]
        if any(i.get("oid") == node.oid for i in items):
            self._ud.remove_favorite(node.oid)
            self._status.setText(f"已取消收藏: {node.name}")
        else:
            self._ud.add_favorite({
                "oid": node.oid, "name": node.name,
                "module": node.module_name,
            })
            self._status.setText(f"已收藏: {node.name}")
        self._refresh_favorites()

    def _refresh_favorites(self) -> None:
        items = self._ud.favorites()["items"]
        self._fav_view.setRowCount(len(items))
        for r, it in enumerate(items):
            self._fav_view.setItem(r, 0, QTableWidgetItem(it.get("name", "")))
            self._fav_view.setItem(r, 1, QTableWidgetItem(it.get("oid", "")))

    def _refresh_history(self) -> None:
        items = self._ud.history()["items"]
        self._hist_view.setRowCount(len(items))
        for r, it in enumerate(items):
            self._hist_view.setItem(r, 0, QTableWidgetItem(it.get("oid", "")))
            self._hist_view.setItem(r, 1, QTableWidgetItem(it.get("name", "")))

    def closeEvent(self, event) -> None:
        """关闭时持久化窗口状态:详情显隐、几何、分割比例。"""
        import base64
        cfg = self._ud.config()
        cfg["detail_visible"] = self._detail_btn.isChecked()
        # saveGeometry 返回 QByteArray,转 base64 字符串以便 JSON 序列化
        cfg["window_geometry"] = base64.b64encode(
            bytes(self.saveGeometry())
        ).decode("ascii")
        cfg["split_sizes"] = self._splitter.sizes()
        self._ud.set_config(cfg)
        super().closeEvent(event)

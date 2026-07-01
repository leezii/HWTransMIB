"""主窗口状态记忆测试:展开状态、列宽。"""
import pytest

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.ui.main_window import MainWindow


@pytest.fixture
def make_window(fixtures_mibs_dir, tmp_path):
    """工厂:每次返回新窗口 + UserData。"""
    def _make():
        imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
        return MainWindow(imp, UserData(base_dir=tmp_path))
    return _make


def _build_tree() -> MibNode:
    """构造含 3 层节点的测试树。"""
    root = MibNode("1", "iso", NodeType.SUBTREE)
    a = MibNode("1.3", "org", NodeType.SUBTREE, parent=root)
    b = MibNode("1.3.6", "dod", NodeType.SUBTREE, parent=a)
    c = MibNode("1.3.6.1", "internet", NodeType.SUBTREE, parent=b)
    root.children = [a]
    a.children = [b]
    b.children = [c]
    return root


def _setup_tree(window):
    """给窗口挂一个测试树模型并绑定信号。"""
    from hwtransmib.ui.mib_tree_model import MibTreeModel
    window._model = MibTreeModel(_build_tree())
    window._tree.setModel(window._model)
    window._connect_tree_signals()


def test_expanded_oids_tracked_on_expand(make_window, qtbot):
    """展开节点 → OID 加入 PersistentTreeView 集合。"""
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)
    root_idx = w._tree.model().index(0, 0)
    w._tree.setExpanded(root_idx, True)
    assert "1" in w._tree.expanded_oids()


def test_expanded_oids_removed_on_collapse(make_window, qtbot):
    """折叠节点 → OID 从集合移除。"""
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)
    root_idx = w._tree.model().index(0, 0)
    w._tree.setExpanded(root_idx, True)
    w._tree.setExpanded(root_idx, False)
    assert "1" not in w._tree.expanded_oids()


def test_expanded_state_persisted_on_close(make_window, qtbot):
    """关闭窗口 → 展开状态写入 config。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)
    root_idx = w._tree.model().index(0, 0)
    w._tree.setExpanded(root_idx, True)
    w.closeEvent(QCloseEvent())
    cfg = UserData(base_dir=w._ud._base).config()
    assert "1" in cfg["expanded_oids"]


def test_restore_expanded_skips_missing_oid(make_window, qtbot):
    """恢复时,树中不存在的 OID 静默跳过;存在的立即展开。"""
    w = make_window()
    qtbot.addWidget(w)
    cfg = w._ud.config()
    cfg["expanded_oids"] = ["1.3.6.1", "9.9.9.9"]
    w._ud.set_config(cfg)
    _setup_tree(w)
    w._restore_expanded_state()
    idx_1361 = w._model.index_from_oid("1.3.6.1")
    assert w._tree.isExpanded(idx_1361)


def test_restore_expanded_after_model_set(make_window, qtbot):
    """setModel 后展开状态自动恢复,无需 show/点击。

    PersistentTreeView 在 rowsInserted 时按记录展开,与视图项创建绑定。
    """
    from hwtransmib.ui.mib_tree_model import MibTreeModel
    w = make_window()
    qtbot.addWidget(w)
    cfg = w._ud.config()
    cfg["expanded_oids"] = ["1.3.6"]
    w._ud.set_config(cfg)
    w._model = MibTreeModel(_build_tree())
    w._tree.setModel(w._model)
    w._connect_tree_signals()
    # 恢复(同步,set_expanded_oids 立即对已存在行应用)
    w._restore_expanded_state()
    idx = w._model.index_from_oid("1.3.6")
    assert w._tree.isExpanded(idx)


def test_column_widths_default_ratio_2to1(make_window, qtbot):
    """首次启动(无记录):节点列宽度 ≈ OID 列的 2 倍。"""
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)
    w.show()
    w._apply_column_widths()
    w0 = w._tree.columnWidth(0)
    w1 = w._tree.columnWidth(1)
    # 2:1 比例,允许 ±5px 误差(整数除法)
    assert abs(w0 - 2 * w1) < 6, f"节点列{w0} vs OID列{w1} 比例非 2:1"


def test_column_widths_restored_from_config(make_window, qtbot):
    """有记录时:恢复用户保存的列宽。"""
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)  # 列宽设置需要 model 存在
    cfg = w._ud.config()
    cfg["tree_column_widths"] = [400, 200]
    w._ud.set_config(cfg)
    w._apply_column_widths()
    assert w._tree.columnWidth(0) == 400
    assert w._tree.columnWidth(1) == 200


def test_column_widths_persisted_on_close(make_window, qtbot):
    """关闭时:有效列宽写入 config。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)  # 列宽操作需要 model 存在
    w.show()
    w._apply_column_widths()
    w.closeEvent(QCloseEvent())
    saved = UserData(base_dir=w._ud._base).config()["tree_column_widths"]
    assert saved is not None
    assert len(saved) == 2


def test_history_shows_time_column(make_window, qtbot):
    """历史 Tab 含'时间'列。"""
    w = make_window()
    qtbot.addWidget(w)
    w._ud.add_history_entry({"oid": "1.2.3", "name": "test",
                             "timestamp": 1730000000})
    w._refresh_history()
    headers = [w._hist_view.horizontalHeaderItem(c).text()
               for c in range(w._hist_view.columnCount())]
    assert "时间" in headers


def test_history_time_formatted_readable(make_window, qtbot):
    """时间列显示可读格式(非裸时间戳)。"""
    w = make_window()
    qtbot.addWidget(w)
    w._ud.add_history_entry({"oid": "1.2.3", "name": "test",
                             "timestamp": 1730000000})
    w._refresh_history()
    time_text = w._hist_view.item(0, 0).text()
    assert "-" in time_text or ":" in time_text
    assert "1730000000" not in time_text


def test_history_sorted_by_time_descending(make_window, qtbot):
    """历史按 timestamp 倒序显示(最新在最上)。

    回归: 旧实现依赖存储顺序,timestamp 与插入顺序不一致时乱序。
    """
    w = make_window()
    qtbot.addWidget(w)
    # 乱序插入: a(旧) → c(新) → b(中)
    w._ud.add_history_entry({"oid": "1.1", "name": "a", "timestamp": 1000})
    w._ud.add_history_entry({"oid": "1.3", "name": "c", "timestamp": 3000})
    w._ud.add_history_entry({"oid": "1.2", "name": "b", "timestamp": 2000})
    w._refresh_history()
    # 应按时间倒序: c(3000) → b(2000) → a(1000)
    names = [w._hist_view.item(r, 2).text() for r in range(w._hist_view.rowCount())]
    assert names == ["c", "b", "a"], f"历史未按时间倒序: {names}"


def test_history_missing_timestamp_at_end(make_window, qtbot):
    """无 timestamp 的条目排末尾(防御性)。"""
    w = make_window()
    qtbot.addWidget(w)
    w._ud.add_history_entry({"oid": "1.2", "name": "b", "timestamp": 2000})
    w._ud.add_history_entry({"oid": "1.1", "name": "a"})  # 无 timestamp
    w._refresh_history()
    names = [w._hist_view.item(r, 2).text() for r in range(w._hist_view.rowCount())]
    # 有 timestamp 的在前(b),无 timestamp 的在末(a)
    assert names == ["b", "a"], f"无 timestamp 未排末尾: {names}"


def test_zero_column_widths_ignored(make_window, qtbot):
    """config 里保存的 0 列宽应被忽略(回归: 导致树空白)。

    缺陷: closeEvent 曾保存 [0,0],_apply_column_widths 用 `if saved`
    判断([0,0] 为真),导致 setColumnWidth(0,0) 树内容完全看不见。
    """
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)
    # 预置错误的 0 宽度
    cfg = w._ud.config()
    cfg["tree_column_widths"] = [0, 0]
    w._ud.set_config(cfg)
    w._apply_column_widths()
    # 列宽不应是 0(应回退到 2:1 默认)
    assert w._tree.columnWidth(0) > 0, "节点列宽被设为 0(树会空白)"
    assert w._tree.columnWidth(1) > 0, "OID 列宽被设为 0"


def test_zero_widths_not_persisted_on_close(make_window, qtbot):
    """关闭时若列宽为 0,不保存(存 None)。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    # 强制列宽为 0(模拟异常布局状态)
    w._tree.setColumnWidth(0, 0)
    w._tree.setColumnWidth(1, 0)
    w.closeEvent(QCloseEvent())
    saved = UserData(base_dir=w._ud._base).config()["tree_column_widths"]
    assert saved is None, f"0 宽度不应保存,但存了 {saved}"


from hwtransmib.ui.main_window import format_index


def test_format_index_empty():
    """空索引(标量节点):返回空字符串。"""
    assert format_index({}) == ""


def test_format_index_single():
    """单值索引:一行 '节点名 = 值'。"""
    assert format_index({"ifIndex": "5"}) == "ifIndex = 5"


def test_format_index_compound():
    """联合索引:每组一行。"""
    result = format_index({"ifIndex": "5", "ifDescr": "eth0"})
    assert result == "ifIndex = 5\nifDescr = eth0"


def test_detail_uses_splitter(make_window, qtbot):
    """详情区内部是 QSplitter(可拖动),而非固定 stretch 的 QHBoxLayout。"""
    from PySide6.QtWidgets import QSplitter
    w = make_window()
    qtbot.addWidget(w)
    assert isinstance(w._detail_splitter, QSplitter)


def test_detail_splitter_has_minimum_widths(make_window, qtbot):
    """splitter 两侧 widget 设了最小宽度,避免极窄窗口下被压没。"""
    w = make_window()
    qtbot.addWidget(w)
    assert w._property.minimumWidth() >= 200
    assert w._tabs.minimumWidth() >= 240


def test_history_table_has_four_columns(make_window, qtbot):
    """历史表建为 4 列:时间/OID/节点/索引。"""
    w = make_window()
    qtbot.addWidget(w)
    assert w._hist_view.columnCount() == 4
    headers = [w._hist_view.horizontalHeaderItem(c).text()
               for c in range(4)]
    assert headers == ["时间", "OID", "节点", "索引"]


def test_history_index_column_shows_single(make_window, qtbot):
    """单值索引在'索引'列显示 'ifIndex = 5'。"""
    w = make_window()
    qtbot.addWidget(w)
    w._ud.add_history_entry({
        "oid": "1.2.3.5", "name": "ifDescr",
        "index_values": {"ifIndex": "5"}, "timestamp": 1730000000,
    })
    w._refresh_history()
    assert w._hist_view.item(0, 3).text() == "ifIndex = 5"


def test_history_index_column_shows_compound(make_window, qtbot):
    """联合索引在'索引'列多行显示。"""
    w = make_window()
    qtbot.addWidget(w)
    w._ud.add_history_entry({
        "oid": "1.2.3", "name": "test",
        "index_values": {"ifIndex": "5", "ifDescr": "eth0"},
        "timestamp": 1730000000,
    })
    w._refresh_history()
    index_text = w._hist_view.item(0, 3).text()
    assert index_text == "ifIndex = 5\nifDescr = eth0"


def test_history_index_column_empty_for_scalar(make_window, qtbot):
    """标量节点(无索引)'索引'列留空。"""
    w = make_window()
    qtbot.addWidget(w)
    w._ud.add_history_entry({
        "oid": "1.2.3", "name": "scalar",
        "index_values": {}, "timestamp": 1730000000,
    })
    w._refresh_history()
    assert w._hist_view.item(0, 3).text() == ""


def test_history_index_column_empty_for_legacy_entry(make_window, qtbot):
    """旧记录(无 index_values 字段)'索引'列留空,不报错(向后兼容)。"""
    w = make_window()
    qtbot.addWidget(w)
    # 旧格式:无 index_values 键
    w._ud.add_history_entry({"oid": "1.2.3", "name": "legacy",
                             "timestamp": 1730000000})
    w._refresh_history()
    assert w._hist_view.item(0, 3).text() == ""

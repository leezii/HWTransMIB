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
    """展开节点 → OID 加入内存集合。"""
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)
    root_idx = w._tree.model().index(0, 0)
    w._tree.setExpanded(root_idx, True)
    assert "1" in w._expanded_oids


def test_expanded_oids_removed_on_collapse(make_window, qtbot):
    """折叠节点 → OID 从内存集合移除。"""
    w = make_window()
    qtbot.addWidget(w)
    _setup_tree(w)
    root_idx = w._tree.model().index(0, 0)
    w._tree.setExpanded(root_idx, True)
    w._tree.setExpanded(root_idx, False)
    assert "1" not in w._expanded_oids


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
    """恢复时,树中不存在的 OID 静默跳过。"""
    w = make_window()
    qtbot.addWidget(w)
    # 预置 config 含一个不存在的 OID
    cfg = w._ud.config()
    cfg["expanded_oids"] = ["1.3.6.1", "9.9.9.9"]
    w._ud.set_config(cfg)
    # 加载树并恢复
    _setup_tree(w)
    w._restore_expanded_state()
    # 不应抛异常;存在的 1.3.6.1 应展开
    idx_1361 = w._model.index_from_oid("1.3.6.1")
    assert w._tree.isExpanded(idx_1361)


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
    """关闭时:列宽写入 config。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    w.show()
    w._apply_column_widths()
    w.closeEvent(QCloseEvent())
    saved = UserData(base_dir=w._ud._base).config()["tree_column_widths"]
    assert saved is not None
    assert len(saved) == 2

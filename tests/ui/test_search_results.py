"""搜索结果列表测试。"""
import pytest

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.services.search_service import SearchService
from hwtransmib.ui.main_window import MainWindow
from hwtransmib.ui.mib_tree_model import MibTreeModel


@pytest.fixture
def make_window(fixtures_mibs_dir, tmp_path):
    def _make():
        imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
        return MainWindow(imp, UserData(base_dir=tmp_path))
    return _make


def _build_tree() -> MibNode:
    root = MibNode("1", "iso", NodeType.SUBTREE)
    a = MibNode("1.3.6.1.2.1.2.2.1.2", "ifDescr", NodeType.COLUMN, parent=root)
    b = MibNode("1.3.6.1.2.1.1.1", "sysDescr", NodeType.SCALAR, parent=root)
    root.children = [a, b]
    return root


def test_search_populates_results_list(make_window, qtbot):
    """搜索触发后,结果列表显示匹配项。"""
    w = make_window()
    qtbot.addWidget(w)
    w._model = MibTreeModel(_build_tree())
    w._tree.setModel(w._model)
    w._search_svc = SearchService(root=_build_tree())
    w._on_search("descr")
    assert w._search_results.count() >= 2
    texts = [w._search_results.item(i).text()
             for i in range(w._search_results.count())]
    assert any("ifDescr" in t for t in texts)


def test_search_empty_query_clears_results(make_window, qtbot):
    """空查询清空结果列表。"""
    w = make_window()
    qtbot.addWidget(w)
    w._search_svc = SearchService(root=_build_tree())
    w._on_search("descr")
    assert w._search_results.count() > 0
    w._on_search("")
    assert w._search_results.count() == 0


def test_search_result_click_selects_node(make_window, qtbot):
    """点击结果项跳转到节点。"""
    w = make_window()
    qtbot.addWidget(w)
    w._model = MibTreeModel(_build_tree())
    w._tree.setModel(w._model)
    w._search_svc = SearchService(root=_build_tree())
    w.show()
    w._on_search("ifDescr")
    w._search_results.setCurrentRow(0)
    w._on_search_result_activated()
    cur = w._tree.currentIndex()
    node = w._model.node_from_index(cur)
    assert node.name == "ifDescr"

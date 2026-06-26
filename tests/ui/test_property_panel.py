"""PropertyPanel 索引构成显示测试。"""
import pytest

from hwtransmib.kernel.model import IndexSpec, MibNode, NodeType
from hwtransmib.ui.property_panel import PropertyPanel


def _row_with_index() -> MibNode:
    """构造 ifEntry(ROW)含单列索引 ifIndex。"""
    root = MibNode("1.3.6.1.2.1.2.2.1", "ifEntry", NodeType.ROW,
                   index_specs=[IndexSpec(
                       column_name="ifIndex",
                       column_oid="1.3.6.1.2.1.2.2.1.1",
                       implied=False, syntax="INTEGER",
                   )])
    return root


def _multi_index_row() -> MibNode:
    """构造多列索引 ROW(Integer32 + IpAddress)。"""
    return MibNode("1.3.6.1.2.1.4.22.1", "ipNetToMediaEntry", NodeType.ROW,
                   index_specs=[
                       IndexSpec("ipNetToMediaIfIndex", "1.3.6.1.2.1.4.22.1.1",
                                 implied=False, syntax="Integer32"),
                       IndexSpec("ipNetToMediaNetAddress", "1.3.6.1.2.1.4.22.1.3",
                                 implied=False, syntax="IpAddress"),
                   ])


def _find_row(panel, label: str) -> int:
    """找属性列文本为 label 的行号。"""
    for r in range(panel._table.rowCount()):
        if panel._table.item(r, 0).text() == label:
            return r
    raise AssertionError(f"未找到行: {label}")


def test_row_shows_index_rows(qtbot):
    """ROW 节点显示索引构成行。"""
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.show_node(_row_with_index())
    labels = [panel._table.item(r, 0).text() for r in range(panel._table.rowCount())]
    assert "索引列 1" in labels


def test_row_index_row_content(qtbot):
    """索引行的值含列名、OID、类型。"""
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.show_node(_row_with_index())
    idx = _find_row(panel, "索引列 1")
    value = panel._table.item(idx, 1).text()
    assert "ifIndex" in value
    assert "1.3.6.1.2.1.2.2.1.1" in value
    assert "INTEGER" in value


def test_multi_index_shows_all_rows(qtbot):
    """多列索引显示多行。"""
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.show_node(_multi_index_row())
    labels = [panel._table.item(r, 0).text() for r in range(panel._table.rowCount())]
    assert "索引列 1" in labels
    assert "索引列 2" in labels


def test_scalar_has_no_index_rows(qtbot):
    """SCALAR 节点不显示索引行。"""
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.show_node(MibNode("1.3.6.1.2.1.1.1", "sysDescr", NodeType.SCALAR))
    labels = [panel._table.item(r, 0).text() for r in range(panel._table.rowCount())]
    assert not any("索引" in l for l in labels)


def test_table_shows_child_row_index(qtbot):
    """TABLE 节点自动取子 ROW 的索引,标注来源。"""
    table = MibNode("1.3.6.1.2.1.2.2", "ifTable", NodeType.TABLE)
    row = MibNode("1.3.6.1.2.1.2.2.1", "ifEntry", NodeType.ROW,
                  parent=table, index_specs=[IndexSpec(
                      "ifIndex", "1.3.6.1.2.1.2.2.1.1", False, "INTEGER")])
    table.children = [row]
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.show_node(table)
    labels = [panel._table.item(r, 0).text() for r in range(panel._table.rowCount())]
    # 标注来源行
    assert any("索引构成" in l and "ifEntry" in l for l in labels)
    assert "索引列 1" in labels

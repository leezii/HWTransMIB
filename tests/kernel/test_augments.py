"""AUGMENTS 增强表回归测试。

锁定 PySnmp 对 AUGMENTS 的处理:增强表行(ifXEntry)继承被增强表(ifEntry)
的 INDEX。用 IF-MIB 的 ifXTable(AUGMENTS { ifEntry })验证。

背景: PySnmp 7.1 的 registerAugmentions 在 load_modules 时把被增强表的
INDEX 复制给增强表行的 indexNames,我们的 _extract_index_specs 读
indexNames 时自然拿到正确数据。本测试防止未来内核重构破坏该行为。
"""
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import NodeType
from hwtransmib.kernel.oid_builder import OidBuilder
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def root(fixtures_mibs_dir):
    parser = MibParser(extra_sources=[str(fixtures_mibs_dir)])
    parser.parse(["IF-MIB"])
    return MibTreeBuilder(parser).build()


def test_augmented_row_inherits_index(root):
    """增强表行 ifXEntry(AUGMENTS ifEntry)的 index_specs 含 ifIndex。"""
    xentry = root.find("1.3.6.1.2.1.31.1.1.1")  # ifXEntry
    assert xentry is not None
    assert xentry.node_type == NodeType.ROW
    assert xentry.index_specs is not None
    assert len(xentry.index_specs) == 1
    assert xentry.index_specs[0].column_name == "ifIndex"


def test_augmented_column_is_constructible(root):
    """增强表列 ifName 可构造。"""
    ifname = root.find("1.3.6.1.2.1.31.1.1.1.18")  # ifName
    assert ifname is not None
    assert ifname.node_type == NodeType.COLUMN
    assert ifname.is_constructible is True


def test_augmented_column_oid_construction(root, fixtures_mibs_dir):
    """ifName 用继承的 ifIndex 构造正确 OID。

    ifName.ifIndex=5 → 1.3.6.1.2.1.31.1.1.1.18.5
    """
    parser = MibParser(extra_sources=[str(fixtures_mibs_dir)])
    parser.parse(["IF-MIB"])
    builder = OidBuilder(parser=parser, root=root)
    ifname = root.find("1.3.6.1.2.1.31.1.1.1.18")
    oid = builder.build(ifname, {"ifIndex": "5"})
    assert oid == "1.3.6.1.2.1.31.1.1.1.18.5"


def test_augmented_table_property_panel(root, qtbot):
    """ifXTable(TABLE)属性面板显示来自 ifXEntry 的索引构成。"""
    from hwtransmib.ui.property_panel import PropertyPanel

    xtable = root.find("1.3.6.1.2.1.31.1.1")  # ifXTable
    assert xtable is not None
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.show_node(xtable)
    labels = [
        panel._table.item(r, 0).text()
        for r in range(panel._table.rowCount())
    ]
    # 标注来源(来自 ifXEntry)
    assert any("索引构成" in l and "ifXEntry" in l for l in labels)
    assert "索引列 1" in labels

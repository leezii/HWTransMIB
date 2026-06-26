# 属性面板显示索引构成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 TABLE/ROW 类型节点的属性面板显示索引构成(列名/OID/类型/IMPLIED),帮助用户理解 OID 构造的索引来源。

**Architecture:** 纯 UI 层改动。PropertyPanel.show_node 在现有键值对表格末尾追加索引构成行。ROW 直接用 node.index_specs;TABLE 自动取子 ROW 的 index_specs。数据已由 MibBuilder/TreeBuilder 就绪,无需内核改动。

**Tech Stack:** PySide6、pytest-qt。

**参考规格:** `docs/superpowers/specs/2026-06-26-index-display-design.md`

---

## 文件结构

```
src/hwtransmib/ui/property_panel.py   # 修改: show_node 增加索引行 + TABLE 取子 ROW
tests/ui/test_property_panel.py       # 新增: 索引显示测试
```

---

## Task 1: PropertyPanel 显示索引构成

**Files:**
- Modify: `src/hwtransmib/ui/property_panel.py`
- Test: `tests/ui/test_property_panel.py`

- [ ] **Step 1: 编写失败测试**

创建 `tests/ui/test_property_panel.py`:

```python
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


def test_row_shows_index_rows(qtbot):
    """ROW 节点显示索引构成行。"""
    panel = PropertyPanel()
    qtbot.addWidget(panel)
    panel.show_node(_row_with_index())
    # 表格应含"索引列 1"行
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


def _find_row(panel, label: str) -> int:
    """找属性列文本为 label 的行号。"""
    for r in range(panel._table.rowCount()):
        if panel._table.item(r, 0).text() == label:
            return r
    raise AssertionError(f"未找到行: {label}")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/ui/test_property_panel.py -v`
Expected: FAIL(`show_node` 未追加索引行,断言失败)。

- [ ] **Step 3: 修改 PropertyPanel.show_node 增加索引构成**

将 `src/hwtransmib/ui/property_panel.py` 的 `show_node` 方法替换为以下完整实现(在原 rows 列表之后追加索引来源与索引列行):

```python
    def show_node(self, node: MibNode) -> None:
        """填充属性表格,含索引构成(ROW/TABLE 节点)。"""
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

        # 追加索引构成(ROW 直接取,TABLE 取子 ROW)
        index_specs, source_row = self._resolve_index_specs(node)
        if source_row is not None:
            rows.append(("索引构成", f"来自 {source_row.name}"))
        if index_specs:
            for i, spec in enumerate(index_specs, start=1):
                value = f"{spec.column_name} ({spec.column_oid}) · {spec.syntax}"
                if spec.implied:
                    value += " · IMPLIED"
                rows.append((f"索引列 {i}", value))
        elif source_row is not None:
            rows.append(("索引构成", "无"))

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

    def _resolve_index_specs(self, node: MibNode):
        """返回 (index_specs, source_row)。

        ROW:直接用 node.index_specs,source_row=node。
        TABLE:取第一个 ROW 子节点的 index_specs,source_row=该子节点。
        其他:返回 (None, None)。
        """
        if node.node_type == NodeType.ROW:
            return node.index_specs, node
        if node.node_type == NodeType.TABLE:
            for child in node.children:
                if child.node_type == NodeType.ROW and child.index_specs is not None:
                    return child.index_specs, child
            return None, node  # TABLE 但无 ROW 子节点
        return None, None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/ui/test_property_panel.py -v`
Expected: 6 passed。

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `uv run pytest`
Expected: 全部 passed(原 103 + 新增 6 = 109)。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(ui): show index composition in property panel for ROW/TABLE nodes"
```

---

## 自审清单(对照规格)

- [x] ROW 显示索引行 → Task 1 Step 3(`node.node_type == ROW` 分支)
- [x] TABLE 取子 ROW 标注来源 → Task 1 Step 3(`TABLE` 分支 + "来自 {name}")
- [x] SCALAR 不显示 → Task 1 Step 1(test_scalar_has_no_index_rows)
- [x] 多列索引全显示 → Task 1 Step 3(enumerate 追加多行)
- [x] IMPLIED 标记 → Task 1 Step 3(`if spec.implied: value += " · IMPLIED"`)
- [x] 103 测试不回归 → Task 1 Step 5 全量验证
- [x] 无内核改动 → 仅 property_panel.py
- [x] 无占位符 → 每步含完整代码

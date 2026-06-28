# 中优先级优化(4 项)实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 4 项中优先级优化:IMPLIED 测试覆盖、历史排序时间列、搜索结果列表、搜索性能基准评估。

**Architecture:** #5 纯测试(内核已正确);#6/#4 UI 增强(main_window.py);#3 性能基准(先测后定,YAGNI)。每项独立提交,失败不影响其他。

**Tech Stack:** PySide6、pytest-qt、Python time 基准。

**参考规格:** `docs/superpowers/specs/2026-06-28-medium-priority-optimizations-design.md`

---

## 文件结构

```
tests/fixtures/mibs/SNMP-COMMUNITY-MIB     # 已存在(#5 测试数据)
tests/kernel/test_implied_index.py          # 新增 #5
src/hwtransmib/ui/main_window.py            # 修改 #6 历史列 + #4 搜索列表
tests/ui/test_main_window_state.py          # 修改 #6 新增历史测试
tests/ui/test_search_results.py             # 新增 #4
tests/perf/bench_search.py                  # 新增 #3 基准
```

---

## Task 1: #5 IMPLIED 索引测试覆盖

**Files:**
- Test: `tests/kernel/test_implied_index.py`(使用已有 fixture `SNMP-COMMUNITY-MIB`)

- [ ] **Step 1: 编写测试**

创建 `tests/kernel/test_implied_index.py`:

```python
"""IMPLIED 索引测试。

SNMP-COMMUNITY-MIB 的 snmpCommunityEntry 用 `INDEX { IMPLIED snmpCommunityIndex }`。
IMPLIED 字符串索引在 OID 编码时省略长度前缀(P ySnmp 自动处理)。
本测试锁定该行为。
"""
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import NodeType
from hwtransmib.kernel.oid_builder import OidBuilder
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def root(fixtures_mibs_dir):
    parser = MibParser(
        extra_sources=[str(fixtures_mibs_dir),
                       "src/hwtransmib/kernel/standard_mibs"]
    )
    parser.parse(["SNMP-COMMUNITY-MIB"])
    return MibTreeBuilder(parser).build()


def test_implied_flag_captured(root):
    """snmpCommunityEntry 的 index_specs[0].implied == True。"""
    entry = root.find("1.3.6.1.6.3.18.1.1.1")  # snmpCommunityEntry
    assert entry is not None
    assert entry.node_type == NodeType.ROW
    assert entry.index_specs is not None
    assert len(entry.index_specs) == 1
    assert entry.index_specs[0].implied is True
    assert entry.index_specs[0].column_name == "snmpCommunityIndex"


def test_implied_string_oid_no_length_prefix(root, fixtures_mibs_dir):
    """IMPLIED 字符串索引构造无长度前缀。

    snmpCommunityName(列)用 IMPLIED 索引 'public':
    'public' → ASCII 112.117.98.108.105.99(无长度前缀 6)
    """
    parser = MibParser(
        extra_sources=[str(fixtures_mibs_dir),
                       "src/hwtransmib/kernel/standard_mibs"]
    )
    parser.parse(["SNMP-COMMUNITY-MIB"])
    builder = OidBuilder(parser=parser, root=root)
    col = root.find("1.3.6.1.6.3.18.1.1.1.2")  # snmpCommunityName
    assert col is not None
    oid = builder.build(col, {"snmpCommunityIndex": "public"})
    expected_suffix = ".".join(str(ord(c)) for c in "public")
    assert oid == f"1.3.6.1.6.3.18.1.1.1.2.{expected_suffix}"
    # 关键:无长度前缀(非 6.112.117...)
    assert ".6.112." not in oid
```

- [ ] **Step 2: 运行测试验证通过**

Run: `uv run pytest tests/kernel/test_implied_index.py -v`
Expected: 2 passed(功能已正确,仅补覆盖)。

- [ ] **Step 3: 全量回归**

Run: `uv run pytest`
Expected: 全部 passed(原 115 + 2 = 117)。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: add IMPLIED index regression tests (SNMP-COMMUNITY-MIB)"
```

---

## Task 2: #6 历史排序(时间列)

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py:151-153,376-381`
- Test: `tests/ui/test_main_window_state.py`

- [ ] **Step 1: 追加失败测试**

在 `tests/ui/test_main_window_state.py` 末尾追加:

```python
def test_history_shows_time_column(make_window, qtbot):
    """历史 Tab 含'时间'列。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    # 构造历史(需走 closeEvent 落盘后再读,或直接测 _refresh_history)
    from hwtransmib.kernel.model import MibNode, NodeType
    node = MibNode("1.2.3", "test", NodeType.SCALAR)
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
    # 时间在第一列
    time_text = w._hist_view.item(0, 0).text()
    # 应为可读格式(含 - 或 :),非纯数字 1730000000
    assert "-" in time_text or ":" in time_text
    assert "1730000000" not in time_text
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/ui/test_main_window_state.py::test_history_shows_time_column -v`
Expected: FAIL(当前历史 2 列,无"时间")。

- [ ] **Step 3: 修改历史 Tab 为 3 列**

将 `main_window.py:151-153` 的 `_hist_view` 定义改为:

```python
        self._hist_view = QTableWidget(0, 3)
        self._hist_view.setHorizontalHeaderLabels(["时间", "OID", "节点"])
        self._hist_view.verticalHeader().setVisible(False)
```

- [ ] **Step 4: 修改 _refresh_history 填充时间列**

将 `main_window.py:376-381` 的 `_refresh_history` 改为:

```python
    def _refresh_history(self) -> None:
        from datetime import datetime
        items = self._ud.history()["items"]
        self._hist_view.setRowCount(len(items))
        for r, it in enumerate(items):
            ts = it.get("timestamp")
            time_text = ""
            if ts:
                time_text = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
            self._hist_view.setItem(r, 0, QTableWidgetItem(time_text))
            self._hist_view.setItem(r, 1, QTableWidgetItem(it.get("oid", "")))
            self._hist_view.setItem(r, 2, QTableWidgetItem(it.get("name", "")))
```

- [ ] **Step 5: 运行测试验证通过**

Run: `uv run pytest tests/ui/test_main_window_state.py -v -k history`
Expected: 2 passed。

- [ ] **Step 6: 全量回归**

Run: `uv run pytest`
Expected: 全部 passed。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(ui): add time column to history tab (formatted timestamp)"
```

---

## Task 3: #4 搜索结果列表

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py`
- Test: `tests/ui/test_search_results.py`

- [ ] **Step 1: 编写失败测试**

创建 `tests/ui/test_search_results.py`:

```python
"""搜索结果列表测试。"""
import pytest

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
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
    from hwtransmib.services.search_service import SearchService
    w = make_window()
    qtbot.addWidget(w)
    w._model = MibTreeModel(_build_tree())
    w._tree.setModel(w._model)
    w._search_svc = SearchService(root=_build_tree())
    # 触发搜索 "descr"(匹配 ifDescr + sysDescr)
    w._on_search("descr")
    # 结果列表应有内容
    assert w._search_results.count() >= 2
    # 至少含 ifDescr
    texts = [w._search_results.item(i).text() for i in range(w._search_results.count())]
    assert any("ifDescr" in t for t in texts)


def test_search_empty_query_clears_results(make_window, qtbot):
    """空查询清空结果列表。"""
    from hwtransmib.services.search_service import SearchService
    w = make_window()
    qtbot.addWidget(w)
    w._search_svc = SearchService(root=_build_tree())
    w._on_search("descr")
    assert w._search_results.count() > 0
    w._on_search("")
    assert w._search_results.count() == 0


def test_search_result_click_selects_node(make_window, qtbot):
    """点击结果项跳转到节点。"""
    from hwtransmib.services.search_service import SearchService
    w = make_window()
    qtbot.addWidget(w)
    w._model = MibTreeModel(_build_tree())
    w._tree.setModel(w._model)
    w._search_svc = SearchService(root=_build_tree())
    w.show()
    w._on_search("ifDescr")
    # 模拟点击第一项
    w._search_results.setCurrentRow(0)
    w._on_search_result_activated()
    # 树应选中 ifDescr
    cur = w._tree.currentIndex()
    node = w._model.node_from_index(cur)
    assert node.name == "ifDescr"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/ui/test_search_results.py -v`
Expected: FAIL(无 `_search_results` / `_on_search_result_activated`)。

- [ ] **Step 3: 在 MainWindow 添加搜索结果列表 UI**

在 `main_window.py` 的工具栏区域(SearchBox 之后)添加结果列表。找到 `toolbar.addWidget(self._search, 1)` 之后,追加:

```python
        self._search = SearchBox()
        self._search.search_requested.connect(self._on_search)
        toolbar.addWidget(self._search, 1)
        # 搜索结果列表(SearchBox 下方,默认隐藏)
        from PySide6.QtWidgets import QListWidget
        self._search_results = QListWidget()
        self._search_results.setMaximumHeight(160)
        self._search_results.setVisible(False)
        self._search_results.itemClicked.connect(
            lambda *_: self._on_search_result_activated()
        )
        self._search_results.itemActivated.connect(
            lambda *_: self._on_search_result_activated()
        )
        toolbar.addWidget(self._detail_btn)
```

> 注意:需把原 `toolbar.addWidget(self._detail_btn)` 移到结果列表创建之后(如上)。结果列表放在 search 和 detail_btn 之间。同时在 `__init__` 字段区添加 `self._search_results = None` 占位(或就地创建)。

实际实现:把结果列表创建放在 `_build_detail` 之后、工具栏布局前。为简化,直接在工具栏构建处创建(见 Step 3 代码)。

- [ ] **Step 4: 修改 _on_search 填充结果列表**

将 `main_window.py:277-284` 的 `_on_search` 改为:

```python
    def _on_search(self, query: str) -> None:
        """搜索:填充结果列表,跳转第一项。"""
        if self._search_svc is None or not query:
            self._search_results.clear()
            self._search_results.setVisible(False)
            return
        results = self._search_svc.search(query)
        self._search_results.clear()
        for node in results:
            icon = "🟢" if node.is_constructible else "📁"
            self._search_results.addItem(f"{icon} {node.name} ({node.oid})")
        self._search_results.setVisible(len(results) > 0)
        if results:
            self._select_node(results[0])
```

- [ ] **Step 5: 添加结果项激活处理**

在 `_on_search` 之后添加:

```python
    def _on_search_result_activated(self) -> None:
        """结果列表项被点击/激活:跳转到对应节点。"""
        row = self._search_results.currentRow()
        if row < 0 or self._search_svc is None:
            return
        # 重新搜索取结果(简单实现:存上次结果)
        # 更优:存 _last_search_results
        if not hasattr(self, "_last_search_results") or not self._last_search_results:
            return
        if row < len(self._last_search_results):
            self._select_node(self._last_search_results[row])
```

并在 `_on_search` 里保存上次结果(在填充前):

```python
        self._last_search_results = results
```

(在 `results = self._search_svc.search(query)` 之后加这行。)

- [ ] **Step 6: 在 __init__ 初始化字段**

在 `self._search_svc: SearchService | None = None` 之后加:

```python
        self._last_search_results: list = []
```

- [ ] **Step 7: 运行测试验证通过**

Run: `uv run pytest tests/ui/test_search_results.py -v`
Expected: 3 passed。

- [ ] **Step 8: 全量回归**

Run: `uv run pytest`
Expected: 全部 passed。

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(ui): add search results dropdown list with click-to-jump"
```

---

## Task 4: #3 搜索性能基准(先测后定)

**Files:**
- Create: `tests/perf/bench_search.py`

- [ ] **Step 1: 创建性能基准脚本**

创建 `tests/perf/bench_search.py`:

```python
"""搜索性能基准:测量大 MIB 下的单次搜索耗时。

判断是否需要优化(YAGNI):
- < 50ms: 当前可接受,无需优化
- >= 50ms: 需实现哈希/前缀索引

用法: uv run python tests/perf/bench_search.py
"""
import statistics
import time
from pathlib import Path

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.search_index import SearchIndex
from hwtransmib.kernel.tree_builder import MibTreeBuilder


def main():
    mibs_dir = "tests/fixtures/mibs"
    std_dir = "src/hwtransmib/kernel/standard_mibs"
    parser = MibParser(extra_sources=[mibs_dir, std_dir])
    parser.parse(["IF-MIB"])
    root = MibTreeBuilder(parser).build()

    index = SearchIndex(root)
    node_count = sum(1 for _ in _walk(root))
    print(f"节点数: {node_count}")

    queries = ["if", "Descr", "2.2.1.2", "table", "interface", "MIB"]
    timings = []
    for q in queries:
        for _ in range(100):
            t0 = time.perf_counter()
            index.search(q)
            timings.append(time.perf_counter() - t0)

    avg_ms = statistics.mean(timings) * 1000
    p95_ms = sorted(timings)[int(len(timings) * 0.95)] * 1000
    print(f"平均: {avg_ms:.2f}ms")
    print(f"P95:  {p95_ms:.2f}ms")
    if avg_ms < 50:
        print("结论: <50ms,当前性能可接受,无需优化(YAGNI)")
    else:
        print("结论: >=50ms,建议实现哈希/前缀索引")


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行基准**

Run: `uv run python tests/perf/bench_search.py`
Expected: 输出节点数、平均/P95 耗时、结论。

- [ ] **Step 3: 记录结论**

根据基准结果:
- 若 <50ms:在本文件末尾或规格追加"结论:无需优化"
- 若 ≥50ms:补充 Task 5 实现优化

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "perf: add search benchmark script (measure before optimizing)"
```

---

## 自审清单(对照规格)

- [x] #5 IMPLIED 测试 → Task 1
- [x] #6 历史时间列 → Task 2
- [x] #4 搜索结果列表 → Task 3
- [x] #3 性能基准(先测后定) → Task 4
- [x] 验收 1 IMPLIED → Task 1
- [x] 验收 2 历史时间列 → Task 2
- [x] 验收 3 搜索列表点击跳转 → Task 3
- [x] 验收 4 性能基准报告 → Task 4
- [x] 115 测试不回归 → 各 Task 全量验证
- [x] 无占位符 → 每步含完整代码
- [x] 类型一致 → `_last_search_results` / `_search_results` 跨步骤一致

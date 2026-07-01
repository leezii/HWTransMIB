# 详情区三项优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 详情区三项体验优化——属性/收藏历史分隔条可拖动、历史记录补充索引值、收藏历史表列宽可调且持久化。

**Architecture:** 全部落在 UI 层(`main_window.py`)与持久化层(`user_data.py`)、服务层(`oid_build_service.py`)。沿用项目已有的"config.json 键 + 启动读取 / 关闭写入"惯例(参考现有 `split_sizes`、`tree_column_widths`)。详情区内部 `QHBoxLayout`(固定 stretch)改为可拖动 `QSplitter`;历史 entry 增加 `index_values` 字段;收藏/历史表配 Interactive header + 持久化列宽。无 kernel 改动。

**Tech Stack:** PySide6 (Qt 6.6+), Python ≥ 3.11, pytest + pytest-qt。

---

## 文件结构

| 文件 | 责任 | 改动 |
|---|---|---|
| `src/hwtransmib/services/oid_build_service.py` | OID 构造 + 历史记录编排 | entry 加 `index_values` 字段 |
| `src/hwtransmib/persistence/user_data.py` | 四个 JSON 存储 | config 默认模板补 3 个新键 |
| `src/hwtransmib/ui/main_window.py` | 主窗口布局与渲染 | splitter 改造 + 历史表 3→4 列 + 列宽 + `format_index` + closeEvent 写回 |
| `tests/services/test_oid_build_service.py` | 服务层测试 | 新增 index_values 写入/边界测试 |
| `tests/persistence/test_user_data.py` | 持久化测试 | 新增 config 新字段默认值测试 |
| `tests/ui/test_main_window_state.py` | UI 状态测试 | 新增 `format_index`、列宽、splitter 测试 |

## 任务边界与依赖

任务按依赖顺序排列,必须顺序执行。关键边界决策:**`_build_detail` 方法只在 Task 4 中完整重写一次**(同时落地 splitter + 历史表 4 列 + 最小宽度),避免多个 task 交叉修改同一方法导致 Edit 匹配失败。

- Task 1: persistence 默认键(地基,无依赖)
- Task 2: services index_values(无 UI 依赖)
- Task 3: `format_index` 纯函数(无 UI 依赖)
- Task 4: **重写 `_build_detail`**(splitter + 历史表 4 列定义 + 最小宽度)——依赖 Task 3 已完成(后续渲染需 `format_index`)
- Task 5: `_refresh_history` 渲染索引列(依赖 Task 3 `format_index` + Task 4 历史表已是 4 列)
- Task 6: 表格列宽应用方法(依赖 Task 4 两表已创建)
- Task 7: 启动恢复 + closeEvent 持久化(依赖 Task 4 splitter + Task 6 列宽方法)
- Task 8: 全量回归

---

### Task 1: UserData config 默认模板补充新键

**Files:**
- Modify: `src/hwtransmib/persistence/user_data.py:23-29`
- Test: `tests/persistence/test_user_data.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/persistence/test_user_data.py`:

```python
def test_config_defaults_include_detail_panel_fields(tmp_path):
    ud = UserData(base_dir=tmp_path)
    cfg = ud.config()
    assert cfg["detail_split_sizes"] is None
    assert cfg["fav_column_widths"] is None
    assert cfg["hist_column_widths"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/persistence/test_user_data.py::test_config_defaults_include_detail_panel_fields -v`
Expected: FAIL with `KeyError: 'detail_split_sizes'`

- [ ] **Step 3: Update config default template**

In `src/hwtransmib/persistence/user_data.py`, the `__init__` config default (lines 23-29) currently is:

```python
        self._config = JsonStore(self._base / "config.json", {
            "window_geometry": None,
            "detail_visible": True,
            "split_sizes": None,
            "expanded_oids": [],
            "tree_column_widths": None,
        })
```

Add the three new keys before the closing `})`:

```python
        self._config = JsonStore(self._base / "config.json", {
            "window_geometry": None,
            "detail_visible": True,
            "split_sizes": None,
            "expanded_oids": [],
            "tree_column_widths": None,
            "detail_split_sizes": None,
            "fav_column_widths": None,
            "hist_column_widths": None,
        })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/persistence/test_user_data.py::test_config_defaults_include_detail_panel_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/hwtransmib/persistence/user_data.py tests/persistence/test_user_data.py
git commit -m "feat(persistence): add detail panel config keys (detail_split/fav/hist widths)"
```

---

### Task 2: OidBuildService 记录 index_values

**Files:**
- Modify: `src/hwtransmib/services/oid_build_service.py:37-47`
- Test: `tests/services/test_oid_build_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/services/test_oid_build_service.py`:

```python
def test_build_and_record_stores_index_values(setup):
    """构造并记录时,entry 含 index_values 字段且内容正确。"""
    svc, root, ud = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")  # ifDescr
    svc.build_and_record(node, {"ifIndex": "5"})
    entry = ud.history()["items"][0]
    assert entry["index_values"] == {"ifIndex": "5"}


def test_build_and_record_scalar_empty_index(setup):
    """标量节点(无索引):index_values 为空 dict。"""
    svc, root, ud = setup
    node = root.find("1.3.6.1.2.1.2.1")  # ifNumber 标量
    svc.build_and_record(node, {})
    entry = ud.history()["items"][0]
    assert entry["index_values"] == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/services/test_oid_build_service.py::test_build_and_record_stores_index_values tests/services/test_oid_build_service.py::test_build_and_record_scalar_empty_index -v`
Expected: FAIL with `KeyError: 'index_values'`

- [ ] **Step 3: Add index_values to the history entry**

In `src/hwtransmib/services/oid_build_service.py`, the `build_and_record` method (lines 37-47) currently is:

```python
    def build_and_record(self, node: MibNode,
                         index_values: dict[str, str]) -> str:
        """构造并记录到历史。用于"复制 OID"操作。"""
        oid = self._builder.build(node, index_values)
        self._ud.add_history_entry({
            "oid": oid,
            "name": node.name,
            "module": node.module_name,
            "timestamp": int(time.time()),
        })
        return oid
```

Add the `index_values` field to the entry dict:

```python
    def build_and_record(self, node: MibNode,
                         index_values: dict[str, str]) -> str:
        """构造并记录到历史。用于"复制 OID"操作。"""
        oid = self._builder.build(node, index_values)
        self._ud.add_history_entry({
            "oid": oid,
            "name": node.name,
            "module": node.module_name,
            "index_values": dict(index_values),
            "timestamp": int(time.time()),
        })
        return oid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/services/test_oid_build_service.py -v`
Expected: PASS (all 6 tests including the 2 new ones)

- [ ] **Step 5: Commit**

```bash
git add src/hwtransmib/services/oid_build_service.py tests/services/test_oid_build_service.py
git commit -m "feat(services): record index_values in history entries"
```

---

### Task 3: `format_index` 纯函数 + 单元测试

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py` (add module-level function, after imports / before `class MainWindow`)
- Test: `tests/ui/test_main_window_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_main_window_state.py` (and add the import at the top of the appended block):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_main_window_state.py::test_format_index_empty tests/ui/test_main_window_state.py::test_format_index_single tests/ui/test_main_window_state.py::test_format_index_compound -v`
Expected: FAIL with `ImportError: cannot import name 'format_index' from 'hwtransmib.ui.main_window'`

- [ ] **Step 3: Add `format_index` module-level function**

In `src/hwtransmib/ui/main_window.py`, insert this function after the imports block (after line 33, the blank line before `class MainWindow`):

```python
def format_index(values: dict[str, str]) -> str:
    """格式化索引值为多行文本:联合索引每组一行 '节点名 = 值'。

    空索引返回空字符串。用于历史表"索引"列显示。
    """
    if not values:
        return ""
    return "\n".join(f"{k} = {v}" for k, v in values.items())


```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_main_window_state.py::test_format_index_empty tests/ui/test_main_window_state.py::test_format_index_single tests/ui/test_main_window_state.py::test_format_index_compound -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hwtransmib/ui/main_window.py tests/ui/test_main_window_state.py
git commit -m "feat(ui): add format_index helper for index column display"
```

---

### Task 4: 重写 `_build_detail` —— 可拖动 splitter + 历史表 4 列

本任务一次性完成 DET-1(splitter)的创建部分,以及历史表从 3 列改为 4 列(新增"索引"列)的定义。`_build_detail` 在此之后不再被其他 task 修改。

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py:153-170` (`_build_detail`)
- Test: `tests/ui/test_main_window_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_main_window_state.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_main_window_state.py::test_detail_uses_splitter tests/ui/test_main_window_state.py::test_detail_splitter_has_minimum_widths tests/ui/test_main_window_state.py::test_history_table_has_four_columns -v`
Expected: FAIL — `_detail_splitter` attribute missing, history table is 3 columns.

- [ ] **Step 3: Rewrite `_build_detail`**

In `src/hwtransmib/ui/main_window.py`, the `_build_detail` method (lines 153-170) currently is:

```python
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
        self._hist_view = QTableWidget(0, 3)
        self._hist_view.setHorizontalHeaderLabels(["时间", "OID", "节点"])
        self._hist_view.verticalHeader().setVisible(False)
        self._tabs.addTab(self._fav_view, "★ 收藏")
        self._tabs.addTab(self._hist_view, "🕑 历史")
        layout.addWidget(self._tabs, 2)
        return box
```

Replace the entire method with:

```python
    def _build_detail(self) -> QWidget:
        """构建详情区:左属性面板 + 右收藏/历史 Tab,中间可拖动分隔。"""
        box = QGroupBox("详情")
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(4, 4, 4, 4)
        self._property = PropertyPanel()
        self._property.setMinimumWidth(200)
        self._tabs = QTabWidget()
        self._tabs.setMinimumWidth(240)
        self._fav_view = QTableWidget(0, 2)
        self._fav_view.setHorizontalHeaderLabels(["节点", "OID"])
        self._fav_view.verticalHeader().setVisible(False)
        self._hist_view = QTableWidget(0, 4)
        self._hist_view.setHorizontalHeaderLabels(["时间", "OID", "节点", "索引"])
        self._hist_view.verticalHeader().setVisible(False)
        self._hist_view.setWordWrap(True)
        self._tabs.addTab(self._fav_view, "★ 收藏")
        self._tabs.addTab(self._hist_view, "🕑 历史")
        # 水平 splitter:属性面板 ↔ 收藏/历史 Tab,可拖动调节宽度
        self._detail_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._detail_splitter.addWidget(self._property)
        self._detail_splitter.addWidget(self._tabs)
        box_layout.addWidget(self._detail_splitter)
        return box
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_main_window_state.py::test_detail_uses_splitter tests/ui/test_main_window_state.py::test_detail_splitter_has_minimum_widths tests/ui/test_main_window_state.py::test_history_table_has_four_columns -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run full UI suite to confirm no regression from layout change**

Run: `pytest tests/ui/test_main_window_state.py -v`
Expected: PASS (all tests). Existing `test_history_*` tests still pass — they query `item(r, 2)` for the name column (unchanged) and check headers contain "时间" (still present).

- [ ] **Step 6: Commit**

```bash
git add src/hwtransmib/ui/main_window.py tests/ui/test_main_window_state.py
git commit -m "feat(ui): draggable splitter in detail panel + 4-column history table"
```

---

### Task 5: `_refresh_history` 渲染"索引"列

历史表现在已是 4 列(Task 4)。本任务填充第 4 列(索引),并让多行索引行高自适应。

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py:407-421` (`_refresh_history`)
- Test: `tests/ui/test_main_window_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_main_window_state.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_main_window_state.py::test_history_index_column_shows_single tests/ui/test_main_window_state.py::test_history_index_column_shows_compound tests/ui/test_main_window_state.py::test_history_index_column_empty_for_scalar tests/ui/test_main_window_state.py::test_history_index_column_empty_for_legacy_entry -v`
Expected: FAIL — column 3 has no item set (`item(0, 3)` is None or empty).

- [ ] **Step 3: Populate index column in `_refresh_history`**

In `src/hwtransmib/ui/main_window.py`, the `_refresh_history` method (lines 407-421) currently is:

```python
    def _refresh_history(self) -> None:
        from datetime import datetime
        items = self._ud.history()["items"]
        # 按 timestamp 倒序(最新在最上);无 timestamp 的排末尾。
        # 不依赖存储顺序(LRU 插入在 timestamp 与顺序不一致时不可靠)。
        items = sorted(items, key=lambda e: e.get("timestamp") or 0, reverse=True)
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

Replace the entire method with (adds index column population + row-height adjust):

```python
    def _refresh_history(self) -> None:
        from datetime import datetime
        items = self._ud.history()["items"]
        # 按 timestamp 倒序(最新在最上);无 timestamp 的排末尾。
        # 不依赖存储顺序(LRU 插入在 timestamp 与顺序不一致时不可靠)。
        items = sorted(items, key=lambda e: e.get("timestamp") or 0, reverse=True)
        self._hist_view.setRowCount(len(items))
        for r, it in enumerate(items):
            ts = it.get("timestamp")
            time_text = ""
            if ts:
                time_text = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
            self._hist_view.setItem(r, 0, QTableWidgetItem(time_text))
            self._hist_view.setItem(r, 1, QTableWidgetItem(it.get("oid", "")))
            self._hist_view.setItem(r, 2, QTableWidgetItem(it.get("name", "")))
            # 索引列:旧记录无 index_values 键时 .get() 兜底为空(向后兼容)
            index_text = format_index(it.get("index_values", {}))
            self._hist_view.setItem(r, 3, QTableWidgetItem(index_text))
        # 多行索引:行高自适应内容
        self._hist_view.resizeRowsToContents()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_main_window_state.py::test_history_index_column_shows_single tests/ui/test_main_window_state.py::test_history_index_column_shows_compound tests/ui/test_main_window_state.py::test_history_index_column_empty_for_scalar tests/ui/test_main_window_state.py::test_history_index_column_empty_for_legacy_entry -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run full UI suite for regression**

Run: `pytest tests/ui/test_main_window_state.py -v`
Expected: PASS (all tests, including existing sort/time tests which use `item(r, 2)`)

- [ ] **Step 6: Commit**

```bash
git add src/hwtransmib/ui/main_window.py tests/ui/test_main_window_state.py
git commit -m "feat(ui): render index column in history with multi-line support"
```

---

### Task 6: 收藏/历史表列宽配置(Interactive + 默认比例)

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py` (add methods after `_apply_column_widths`, ~line 234)
- Test: `tests/ui/test_main_window_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_main_window_state.py`:

```python
def test_fav_column_widths_default_ratio(make_window, qtbot):
    """首次启动:收藏表节点列 ≈ OID 列(0.55/0.45)。"""
    w = make_window()
    qtbot.addWidget(w)
    w.show()
    w._apply_fav_column_widths()
    total = w._fav_view.columnWidth(0) + w._fav_view.columnWidth(1)
    ratio0 = w._fav_view.columnWidth(0) / total
    # 节点列约占 0.55,允许误差
    assert 0.45 < ratio0 < 0.65, f"节点列占比 {ratio0} 非 ~0.55"


def test_hist_column_widths_default_ratio(make_window, qtbot):
    """首次启动:历史表 OID 列(index 1)占比最大(~0.35)。"""
    w = make_window()
    qtbot.addWidget(w)
    w.show()
    w._apply_hist_column_widths()
    widths = [w._hist_view.columnWidth(c) for c in range(4)]
    total = sum(widths)
    assert total > 0
    ratios = [x / total for x in widths]
    # OID 列(第 2 列,index 1)应最大
    assert ratios[1] > ratios[0], "OID 列应比时间列宽"
    assert ratios[1] > ratios[2], "OID 列应比节点列宽"
    assert ratios[1] > ratios[3], "OID 列应比索引列宽"


def test_fav_column_widths_restored_from_config(make_window, qtbot):
    """有记录时:收藏表恢复用户保存的列宽。"""
    w = make_window()
    qtbot.addWidget(w)
    cfg = w._ud.config()
    cfg["fav_column_widths"] = [300, 250]
    w._ud.set_config(cfg)
    w._apply_fav_column_widths()
    assert w._fav_view.columnWidth(0) == 300
    assert w._fav_view.columnWidth(1) == 250


def test_hist_column_widths_restored_from_config(make_window, qtbot):
    """有记录时:历史表恢复用户保存的列宽。"""
    w = make_window()
    qtbot.addWidget(w)
    cfg = w._ud.config()
    cfg["hist_column_widths"] = [100, 250, 150, 200]
    w._ud.set_config(cfg)
    w._apply_hist_column_widths()
    assert w._hist_view.columnWidth(0) == 100
    assert w._hist_view.columnWidth(1) == 250
    assert w._hist_view.columnWidth(2) == 150
    assert w._hist_view.columnWidth(3) == 200


def test_table_column_widths_zero_ignored(make_window, qtbot):
    """config 里含 0 宽度的列宽应被忽略(回退默认)。"""
    w = make_window()
    qtbot.addWidget(w)
    cfg = w._ud.config()
    cfg["fav_column_widths"] = [0, 0]
    w._ud.set_config(cfg)
    w._apply_fav_column_widths()
    assert w._fav_view.columnWidth(0) > 0, "0 宽度应被忽略回退默认"
    assert w._fav_view.columnWidth(1) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_main_window_state.py -k "fav_column or hist_column" -v`
Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute '_apply_fav_column_widths'`

- [ ] **Step 3: Add column-width application methods**

In `src/hwtransmib/ui/main_window.py`, after the `_apply_column_widths` method ends (after line 233), add these three methods:

```python
    @staticmethod
    def _apply_table_column_widths(table: QTableWidget, saved: list | None,
                                   ratios: list[float],
                                   fallback_width: int = 600) -> None:
        """通用列宽应用:Interactive 模式 + 持久化 + 默认比例回退。

        saved 为空/长度不符/含非正值时,按 ratios 比例 × fallback_width 分配。
        """
        from PySide6.QtWidgets import QHeaderView
        header = table.horizontalHeader()
        for col in range(table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)

        total = max(table.viewport().width(), fallback_width)
        if (saved and len(saved) == len(ratios) and all(w > 0 for w in saved)):
            for col, w in enumerate(saved):
                table.setColumnWidth(col, w)
        else:
            for col, ratio in enumerate(ratios):
                table.setColumnWidth(col, int(total * ratio))

    def _apply_fav_column_widths(self) -> None:
        """收藏表列宽:[节点 0.55, OID 0.45]。"""
        saved = self._ud.config().get("fav_column_widths")
        self._apply_table_column_widths(
            self._fav_view, saved, [0.55, 0.45])

    def _apply_hist_column_widths(self) -> None:
        """历史表列宽:[时间 0.15, OID 0.35, 节点 0.20, 索引 0.30]。"""
        saved = self._ud.config().get("hist_column_widths")
        self._apply_table_column_widths(
            self._hist_view, saved, [0.15, 0.35, 0.20, 0.30])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ui/test_main_window_state.py -k "fav_column or hist_column" -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/hwtransmib/ui/main_window.py tests/ui/test_main_window_state.py
git commit -m "feat(ui): configurable column widths for favorites/history tables"
```

---

### Task 7: 启动恢复 + closeEvent 持久化(splitter + 列宽)

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py` (add `_apply_detail_split`; call apply methods at 3 startup sites; extend `closeEvent` at lines 423-438)
- Test: `tests/ui/test_main_window_state.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/ui/test_main_window_state.py`:

```python
def test_detail_split_restored_from_config(make_window, qtbot):
    """_apply_detail_split 恢复详情区 splitter 比例。"""
    w = make_window()
    qtbot.addWidget(w)
    cfg = w._ud.config()
    cfg["detail_split_sizes"] = [400, 300]
    w._ud.set_config(cfg)
    w._apply_detail_split()
    sizes = w._detail_splitter.sizes()
    assert sizes[0] == 400
    assert sizes[1] == 300


def test_detail_split_persisted_on_close(make_window, qtbot):
    """关闭时详情区 splitter 比例写入 config。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    w.show()
    w._apply_detail_split()
    # 模拟用户拖动
    w._detail_splitter.setSizes([500, 350])
    w.closeEvent(QCloseEvent())
    saved = UserData(base_dir=w._ud._base).config()["detail_split_sizes"]
    assert saved == [500, 350]


def test_fav_column_widths_persisted_on_close(make_window, qtbot):
    """关闭时收藏表列宽写入 config。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    w.show()
    w._apply_fav_column_widths()
    w.closeEvent(QCloseEvent())
    saved = UserData(base_dir=w._ud._base).config()["fav_column_widths"]
    assert saved is not None and len(saved) == 2 and all(x > 0 for x in saved)


def test_hist_column_widths_persisted_on_close(make_window, qtbot):
    """关闭时历史表列宽写入 config。"""
    from PySide6.QtGui import QCloseEvent
    w = make_window()
    qtbot.addWidget(w)
    w.show()
    w._apply_hist_column_widths()
    w.closeEvent(QCloseEvent())
    saved = UserData(base_dir=w._ud._base).config()["hist_column_widths"]
    assert saved is not None and len(saved) == 4 and all(x > 0 for x in saved)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ui/test_main_window_state.py::test_detail_split_restored_from_config tests/ui/test_main_window_state.py::test_detail_split_persisted_on_close tests/ui/test_main_window_state.py::test_fav_column_widths_persisted_on_close tests/ui/test_main_window_state.py::test_hist_column_widths_persisted_on_close -v`
Expected: FAIL with `AttributeError: 'MainWindow' object has no attribute '_apply_detail_split'`

- [ ] **Step 3: Add `_apply_detail_split` method**

In `src/hwtransmib/ui/main_window.py`, after the `_apply_hist_column_widths` method (added in Task 6), add:

```python
    def _apply_detail_split(self) -> None:
        """应用详情区 splitter 比例:有记录用记录,否则按当前宽度 6:4。"""
        saved = self._ud.config().get("detail_split_sizes")
        if saved and len(saved) == 2 and saved[0] > 0 and saved[1] > 0:
            self._detail_splitter.setSizes(saved)
        else:
            total = max(self._detail_splitter.width(), 600)
            w0 = total * 6 // 10
            w1 = total - w0
            self._detail_splitter.setSizes([w0, w1])
```

- [ ] **Step 4: Call apply methods at the 3 startup/import sites**

There are 3 places in `src/hwtransmib/ui/main_window.py` that call `self._apply_column_widths()`. After each, add the three detail-panel apply calls.

**(a)** In `__init__`, the block at lines 124-126 currently is:

```python
        self._refresh_favorites()
        self._refresh_history()
        self._apply_column_widths()
```

Change to:

```python
        self._refresh_favorites()
        self._refresh_history()
        self._apply_column_widths()
        self._apply_detail_split()
        self._apply_fav_column_widths()
        self._apply_hist_column_widths()
```

**(b)** In `_auto_reload_imports`, the line (currently ~line 142) inside the `if report.loaded_modules:` block:

```python
            self._apply_column_widths()
```

Change to:

```python
            self._apply_column_widths()
            self._apply_detail_split()
            self._apply_fav_column_widths()
            self._apply_hist_column_widths()
```

**(c)** In `_on_import`, the line (currently ~line 252) in the method body:

```python
        self._apply_column_widths()
```

Change to:

```python
        self._apply_column_widths()
        self._apply_detail_split()
        self._apply_fav_column_widths()
        self._apply_hist_column_widths()
```

- [ ] **Step 5: Persist in `closeEvent`**

In `src/hwtransmib/ui/main_window.py`, the `closeEvent` method (lines 423-438) currently is:

```python
    def closeEvent(self, event) -> None:
        """关闭时持久化窗口状态:详情显隐、几何、分割比例、展开状态。"""
        import base64
        cfg = self._ud.config()
        cfg["detail_visible"] = self._detail_btn.isChecked()
        # saveGeometry 返回 QByteArray,转 base64 字符串以便 JSON 序列化
        cfg["window_geometry"] = base64.b64encode(
            bytes(self.saveGeometry())
        ).decode("ascii")
        cfg["split_sizes"] = self._splitter.sizes()
        cfg["expanded_oids"] = sorted(self._tree.expanded_oids())
        # 仅保存有效的列宽(防御 0 宽度导致下次树空白)
        w0, w1 = self._tree.columnWidth(0), self._tree.columnWidth(1)
        cfg["tree_column_widths"] = [w0, w1] if (w0 > 0 and w1 > 0) else None
        self._ud.set_config(cfg)
        super().closeEvent(event)
```

Replace with (adds detail split + table widths persistence before `set_config`):

```python
    def closeEvent(self, event) -> None:
        """关闭时持久化窗口状态:详情显隐、几何、分割比例、展开状态、列宽。"""
        import base64
        cfg = self._ud.config()
        cfg["detail_visible"] = self._detail_btn.isChecked()
        # saveGeometry 返回 QByteArray,转 base64 字符串以便 JSON 序列化
        cfg["window_geometry"] = base64.b64encode(
            bytes(self.saveGeometry())
        ).decode("ascii")
        cfg["split_sizes"] = self._splitter.sizes()
        cfg["expanded_oids"] = sorted(self._tree.expanded_oids())
        # 仅保存有效的列宽(防御 0 宽度导致下次树空白)
        w0, w1 = self._tree.columnWidth(0), self._tree.columnWidth(1)
        cfg["tree_column_widths"] = [w0, w1] if (w0 > 0 and w1 > 0) else None
        # 详情区 splitter 比例
        cfg["detail_split_sizes"] = self._detail_splitter.sizes()
        # 收藏/历史表列宽(含 0 宽度时存 None 防御)
        fav_w = [self._fav_view.columnWidth(c)
                 for c in range(self._fav_view.columnCount())]
        cfg["fav_column_widths"] = fav_w if all(x > 0 for x in fav_w) else None
        hist_w = [self._hist_view.columnWidth(c)
                  for c in range(self._hist_view.columnCount())]
        cfg["hist_column_widths"] = hist_w if all(x > 0 for x in hist_w) else None
        self._ud.set_config(cfg)
        super().closeEvent(event)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/ui/test_main_window_state.py -v`
Expected: PASS (all tests including the 4 new ones)

- [ ] **Step 7: Commit**

```bash
git add src/hwtransmib/ui/main_window.py tests/ui/test_main_window_state.py
git commit -m "feat(ui): persist detail splitter and table column widths"
```

---

### Task 8: 全量回归测试与冒烟验证

**Files:**
- No new files; run full suite

- [ ] **Step 1: Run the complete test suite**

Run: `pytest -v`
Expected: All tests PASS (existing tests + ~20 new tests). Zero failures.

- [ ] **Step 2: Manual smoke test checklist**

Launch the app: `uv run hwtransmib`

Verify each acceptance criterion from the spec:

1. [ ] 详情区属性面板与收藏/历史 Tab 之间出现可拖动分隔条;拖动后关闭重开 → 比例保持。
2. [ ] 构造 OID 时填索引值(如 ifIndex=5)并复制 → 历史 Tab 该记录"索引"列显示 `ifIndex = 5`;联合索引显示多行。
3. [ ] 标量节点构造后,历史"索引"列留空,其他列正常。
4. [ ] 收藏表、历史表各列宽度可单独拖动;OID 列默认占比合理;拖动调整后关闭重开仍保持。
5. [ ] 极窄窗口下属性面板/Tab 区不被压没(最小宽度生效)。

- [ ] **Step 3: Final commit if any fixes needed**

If smoke test revealed issues, fix and commit. Otherwise no commit needed.

---

## Self-Review 结果

**1. Spec coverage:**
- DET-1(可拖动 splitter)→ Task 4(创建 splitter + 最小宽度)+ Task 7(`_apply_detail_split` 持久化/恢复)✓
- DET-2(索引值记录)→ Task 2(写入 entry `index_values`)+ Task 3(`format_index`)+ Task 4(历史表 4 列定义)+ Task 5(渲染索引列 + 多行)✓
- DET-3(列宽可调持久化)→ Task 1(config 3 键)+ Task 6(`_apply_*_column_widths` 方法 + 默认比例)+ Task 7(closeEvent 持久化 + 启动调用)✓
- 向后兼容(旧 entry 无 index_values)→ Task 5 `test_history_index_column_empty_for_legacy_entry`,用 `it.get("index_values", {})` 兜底 ✓
- 最小宽度边界 → Task 4 `test_detail_splitter_has_minimum_widths` ✓
- 0 宽度防御 → Task 6 `test_table_column_widths_zero_ignored` + Task 7 closeEvent `all(x > 0)` 守卫 ✓
- config 默认值 → Task 1 `test_config_defaults_include_detail_panel_fields` ✓

**2. Placeholder scan:** 无 TBD/TODO;所有代码块完整给出 old/new;测试代码完整;命令带预期输出。✓

**3. Type consistency:**
- `format_index(values: dict[str, str]) -> str` — Task 3 定义,Task 5 调用 `format_index(it.get("index_values", {}))` ✓
- `_apply_fav_column_widths` / `_apply_hist_column_widths` — Task 6 定义,Task 7 启动调用 ✓
- `_apply_detail_split` — Task 7 定义并调用 ✓
- `_detail_splitter` — Task 4 创建为 `QSplitter` 实例属性,Task 7 使用 ✓
- 历史表 4 列 — Task 4 定义 `QTableWidget(0, 4)`,Task 5/6/7 全部按 4 列处理 ✓
- QTableWidget 列宽方法名 — 全程使用 `setHorizontalHeaderLabels`(Labels,非 Headers),`columnWidth`,`setColumnWidth`,`columnCount` ✓
- `_apply_table_column_widths` 静态方法签名 — Task 6 定义 `(table, saved, ratios, fallback_width=600)`,内部调用传 3 个位置参数 ✓

**4. 任务边界无冲突:**
- `_build_detail` 仅在 Task 4 完整重写一次(含 splitter + 4 列 + setWordWrap + 最小宽度),后续 task 不再改它 ✓
- `_refresh_history` 仅在 Task 5 修改 ✓
- `closeEvent` 仅在 Task 7 修改 ✓
- 每个 task 的 Edit old_string 都对应前序 task 完成后的稳定状态 ✓

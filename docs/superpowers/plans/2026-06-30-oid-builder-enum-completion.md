# OID 构造对话框 TC 枚举值补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 OID 构造对话框中,带枚举值的 TC 类型索引列(如 `InetVersion`)支持键入少量字符匹配提示枚举名,并接受枚举名或数字编码 OID。

**Architecture:** 内核层一次性把枚举值 `(name, value)` 列表填入 `IndexSpec.named_values`(与既有 `is_integer` 提取同构);内核 `OidBuilder` 放开枚举名校验/编码;UI 层对有枚举的列挂 `QCompleter`,并在读取输入时规范化 `"name (n)"` → `"name"`。四层单向依赖不变,内核可独立测试。

**Tech Stack:** Python 3.11 / PySide6(Qt `QCompleter`)/ PySnmp 7.1(`namedValues`、`getInstIdFromIndices` 接受枚举名)/ pytest + pytest-qt

**Spec:** `docs/superpowers/specs/2026-06-30-oid-builder-enum-completion-design.md`

---

## File Structure

| 文件 | 职责 | 改动类型 |
|---|---|---|
| `src/hwtransmib/kernel/model.py` | `IndexSpec` 增加 `named_values` 字段 | Modify |
| `src/hwtransmib/kernel/tree_builder.py` | 提取 `namedValues` 填入 `IndexSpec` | Modify |
| `src/hwtransmib/kernel/oid_builder.py` | `_coerce`/`_validate_value` 放开枚举名 | Modify |
| `src/hwtransmib/ui/oid_builder_dialog.py` | 挂 `QCompleter` + `_normalize` 规范化 | Modify |
| `tests/kernel/test_tc_integer_detection.py` | 翻转 rejects→accepts + 新增提取断言 | Modify |
| `tests/kernel/test_oid_builder.py` | 新增枚举编码/数字兼容/非法名用例 | Modify |
| `tests/ui/test_oid_builder_dialog.py` | 新增补全器挂载与规范化预览用例 | Modify |

TDD 顺序:每个任务先写失败测试 → 实现 → 测试通过 → 提交。按依赖从底层(内核数据)到上层(UI)推进。

---

## Task 1: `IndexSpec.named_values` 字段

**Files:**
- Modify: `src/hwtransmib/kernel/model.py:19-25`

- [ ] **Step 1: Write the failing test**

追加到 `tests/kernel/test_tc_integer_detection.py` 末尾:

```python
def test_named_values_extracted_for_enum_tc(root):
    """InetVersion(TC 枚举整数)的 named_values 被提取。"""
    entry = root.find("1.3.6.1.2.1.4.31.3.1")  # ipIfStatsEntry
    spec = entry.index_specs[0]  # ipIfStatsIPVersion = InetVersion
    assert spec.named_values == [("unknown", 0), ("ipv4", 1), ("ipv6", 2)]


def test_named_values_empty_for_non_enum_tc(root):
    """InterfaceIndex(无枚举 TC 整数)的 named_values 为空列表。"""
    entry = root.find("1.3.6.1.2.1.4.31.3.1")  # ipIfStatsEntry
    spec = entry.index_specs[1]  # ipIfStatsIfIndex = InterfaceIndex
    assert spec.named_values == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/kernel/test_tc_integer_detection.py::test_named_values_extracted_for_enum_tc tests/kernel/test_tc_integer_detection.py::test_named_values_empty_for_non_enum_tc -v`
Expected: FAIL — `AttributeError: 'IndexSpec' object has no attribute 'named_values'`(因 `tree_builder` 还未填充,即便加了字段也拿到默认空列表,前一个断言会 FAIL)

- [ ] **Step 3: Add `named_values` field to `IndexSpec`**

Edit `src/hwtransmib/kernel/model.py` 的 `IndexSpec`:

```python
@dataclass
class IndexSpec:
    """表的索引列定义。"""
    column_name: str
    column_oid: str
    implied: bool
    syntax: str
    is_integer: bool = False  # 是否整数类型(含 TC 包装,如 InetVersion/InterfaceIndex)
    # 枚举值(名称,数字)列表;空表示无枚举(纯整数,如 InterfaceIndex)
    named_values: list[tuple[str, int]] = field(default_factory=list)
```

(顶部已 `from dataclasses import dataclass, field`,无需新增 import。)

- [ ] **Step 4: Populate `named_values` in tree_builder**

Edit `src/hwtransmib/kernel/tree_builder.py`。`_syntax_info_of_symbol` 扩展为返回三元组:

```python
    def _syntax_info_of_symbol(self, module: str, name: str):
        """返回 (syntax 名, 是否整数类型, 枚举值列表)。

        用 PySnmp syntax 对象的基类链判断整数(准确覆盖 TC 包装类型如
        InetVersion/InterfaceIndex),回退到 syntax 名子串匹配。
        枚举值取自 syntax 对象的 namedValues(如 InetVersion → unknown/ipv4/ipv6)。
        """
        try:
            (sym,) = self._parser.import_symbols(module, name)
            syn = sym.getSyntax()
            syntax_name = type(syn).__name__
            mro_names = [c.__name__ for c in type(syn).__mro__]
            is_integer = any("Integer" in n for n in mro_names)
            named_values = self._extract_named_values(syn)
            return syntax_name, is_integer, named_values
        except error.SmiError:
            return None, False, []

    def _extract_named_values(self, syn) -> list[tuple[str, int]]:
        """从 syntax 对象提取枚举值 (name, value) 列表;无枚举返回空列表。"""
        nv = getattr(syn, "namedValues", None)
        if nv is None:
            return []
        try:
            items = list(nv.items())
        except Exception:
            return []
        return [(str(name), int(value)) for name, value in items]
```

更新 `_extract_index_specs` 调用处与构造(当前是 `col_syntax, is_integer = self._syntax_info_of_symbol(...)`,改为三元组并透传):

```python
    def _extract_index_specs(self, sym) -> list[IndexSpec] | None:
        """从 ROW 节点提取 INDEX 列定义。仅 MibTableRow 有 indexNames。"""
        index_names = getattr(sym, "indexNames", None)
        if not index_names:
            return None
        specs: list[IndexSpec] = []
        for entry in index_names:
            # indexNames 结构: ((implied, module, name), ...)
            implied, mod, col_name = entry[0], entry[1], entry[2]
            col_oid = self._oid_of_symbol(mod, col_name)
            col_syntax, is_integer, named_values = (
                self._syntax_info_of_symbol(mod, col_name)
            )
            specs.append(IndexSpec(
                column_name=col_name, column_oid=col_oid,
                implied=bool(implied), syntax=col_syntax or "INTEGER",
                is_integer=is_integer, named_values=named_values,
            ))
        return specs
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/kernel/test_tc_integer_detection.py -v`
Expected: PASS — 两个新断言通过,既有 `test_tc_integer_flag_detected` 等不受影响。

- [ ] **Step 6: Run full kernel suite to confirm no regression**

Run: `uv run pytest tests/kernel -q`
Expected: PASS(全部既有用例不回归;`tree_builder`/`model` 等测试无影响)。

- [ ] **Step 7: Commit**

```bash
git add src/hwtransmib/kernel/model.py src/hwtransmib/kernel/tree_builder.py tests/kernel/test_tc_integer_detection.py
git commit -m "feat(kernel): extract TC enum named_values into IndexSpec"
```

---

## Task 2: `OidBuilder` 放开枚举名校验与编码

**Files:**
- Modify: `src/hwtransmib/kernel/oid_builder.py:122-140`(`_coerce`、`_validate_value`)
- Modify: `tests/kernel/test_tc_integer_detection.py:47`(`test_tc_integer_rejects_enum_name`)

- [ ] **Step 1: Write the failing test (accepts enum name)**

在 `tests/kernel/test_tc_integer_detection.py` 把原 `test_tc_integer_rejects_enum_name` 改名为 `test_tc_integer_accepts_enum_name` 并翻转断言:

```python
def test_tc_integer_accepts_enum_name(builder, root):
    """TC 整数索引输入枚举名(如 'ipv4')现在应通过校验(放开枚举名)。"""
    col = root.find("1.3.6.1.2.1.4.31.3.1.3")  # ipIfStatsInReceives
    errors = builder.validate(col, {
        "ipIfStatsIPVersion": "ipv4",   # 枚举名
        "ipIfStatsIfIndex": "5",
    })
    assert errors == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/kernel/test_tc_integer_detection.py::test_tc_integer_accepts_enum_name -v`
Expected: FAIL — 当前 `_validate_value` 走 `_looks_integer` → `int("ipv4")` 报错,断言 `errors == []` 不成立。

- [ ] **Step 3: Write failing test for invalid enum name**

追加到 `tests/kernel/test_oid_builder.py` 末尾(复用 `ip_builder` fixture):

```python
def test_enum_name_encoded_correctly(ip_builder):
    """枚举名 ipv4 + 数字 5 → 索引后缀 1.5(PySnmp 接受枚举名)。"""
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.31.3.1.3")  # ipIfStatsInReceives
    result = ip_builder.build(node, {
        "ipIfStatsIPVersion": "ipv4",   # InetVersion 枚举名 → 编码 1
        "ipIfStatsIfIndex": "5",
    })
    assert result == "1.3.6.1.2.1.4.31.3.1.3.1.5"


def test_enum_numeric_still_works(ip_builder):
    """枚举列也接受纯数字输入(数字路径不变)。"""
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.31.3.1.3")
    result = ip_builder.build(node, {
        "ipIfStatsIPVersion": "1",   # 纯数字
        "ipIfStatsIfIndex": "5",
    })
    assert result == "1.3.6.1.2.1.4.31.3.1.3.1.5"


def test_invalid_enum_name_rejected(ip_builder):
    """非枚举名非数字的输入应报错。"""
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.31.3.1.3")
    errors = ip_builder.validate(node, {
        "ipIfStatsIPVersion": "foo",  # 既非枚举名也非数字
        "ipIfStatsIfIndex": "5",
    })
    assert any("枚举名或数字" in e for e in errors)


def test_non_enum_integer_rejection_unchanged(ip_builder):
    """无枚举列(InterfaceIndex)仍走原整数校验,abc 报'需要整数'。"""
    node = _find(ip_builder._root, "1.3.6.1.2.1.4.31.3.1.3")
    errors = ip_builder.validate(node, {
        "ipIfStatsIPVersion": "1",
        "ipIfStatsIfIndex": "abc",  # 无枚举列,非数字
    })
    assert any("需要整数" in e for e in errors)
```

Run: `uv run pytest tests/kernel/test_oid_builder.py::test_enum_name_encoded_correctly tests/kernel/test_oid_builder.py::test_enum_numeric_still_works tests/kernel/test_oid_builder.py::test_invalid_enum_name_rejected tests/kernel/test_oid_builder.py::test_non_enum_integer_rejection_unchanged -v`
Expected: FAIL — 前 3 个用例因当前 `_coerce`/`_validate_value` 行为不符而失败;第 4 个用例当前应已 PASS(回归基线)。

- [ ] **Step 4: Implement `_is_enum_name` helper and adjust `_coerce`**

Edit `src/hwtransmib/kernel/oid_builder.py`。在 `_looks_integer` 之前新增枚举名判断;改写 `_coerce`:

```python
    def _is_enum_name(self, spec, raw: str) -> bool:
        """raw 是否为该列的合法枚举名(仅对带枚举列有效)。"""
        if not spec.named_values:
            return False
        return any(name == raw for name, _ in spec.named_values)

    def _coerce(self, spec, raw: str):
        """将字符串输入转为 PySnmp 期望的索引值类型。

        带枚举的列:枚举名原样返回字符串(PySnmp getInstIdFromIndices 接受枚举名);
        其余按整数处理。
        """
        if self._is_enum_name(spec, raw):
            return raw  # PySnmp 按枚举名编码为对应整数
        if self._looks_integer(spec, raw):
            try:
                return int(raw)
            except ValueError:
                raise OidBuildError(
                    f"{spec.column_name} 需要整数,得到 {raw!r}"
                )
        # 字符串/IP/MAC 直接传字符串,PySnmp 按 INDEX syntax 编码
        return raw
```

- [ ] **Step 5: Implement enum-aware `_validate_value`**

Edit `src/hwtransmib/kernel/oid_builder.py` 的 `_validate_value`:

```python
    def _validate_value(self, spec, raw: str) -> list[str]:
        # 带枚举的列:接受枚举名或纯数字
        if spec.named_values:
            if self._is_enum_name(spec, raw) or raw.lstrip("-").isdigit():
                return []
            return [f"{spec.column_name} 需要枚举名或数字,得到 {raw!r}"]
        # 无枚举列:保持原整数校验
        if self._looks_integer(spec, raw):
            try:
                int(raw)
            except ValueError:
                return [f"{spec.column_name} 需要整数,得到 {raw!r}"]
        return []
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/kernel/test_oid_builder.py tests/kernel/test_tc_integer_detection.py -v`
Expected: PASS — 4 个新增/翻转用例通过;既有 `test_tc_wrapped_integer_does_not_crash`(IP-MIB 的 Integer32 无枚举列走原路径)、IF-MIB ifIndex 用例不回归。

- [ ] **Step 7: Run full kernel suite to confirm no regression**

Run: `uv run pytest tests/kernel -q`
Expected: PASS。

- [ ] **Step 8: Commit**

```bash
git add src/hwtransmib/kernel/oid_builder.py tests/kernel/test_oid_builder.py tests/kernel/test_tc_integer_detection.py
git commit -m "feat(kernel): accept TC enum names in OID index validation/encoding"
```

---

## Task 3: UI 补全器挂载 + 输入规范化

**Files:**
- Modify: `src/hwtransmib/ui/oid_builder_dialog.py:1-99`(imports、`_build_ui`、`_values`、新增 `_normalize`)

- [ ] **Step 1: Write the failing test (completer attached)**

在 `tests/ui/test_oid_builder_dialog.py` 顶部新增一个用 IP-MIB 的 fixture(IP-MIB 含枚举索引列)。先在文件 import 区确认已导入所需(`OidBuilderDialog` 已导入)。

在文件末尾追加(IP-MIB 的 ipIfStatsEntry 第一列是 InetVersion 枚举):

```python
@pytest.fixture
def ip_setup(fixtures_mibs_dir, tmp_path):
    from hwtransmib.persistence.user_data import UserData
    from hwtransmib.services.import_service import ImportService
    from hwtransmib.services.oid_build_service import OidBuildService
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir),
                                      "src/hwtransmib/kernel/standard_mibs"])
    imp.import_files([str(fixtures_mibs_dir / "IP-MIB")])
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    return svc, imp.get_root()


def test_enum_column_has_completer(qtbot, ip_setup):
    """带枚举的索引列(InetVersion)应挂 QCompleter,候选项含 'ipv4 (1)'。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")  # ipIfStatsInReceives COLUMN
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    edit = dlg._inputs["ipIfStatsIPVersion"]
    assert edit.completer() is not None
    model = edit.completer().model()
    labels = [model.data(model.index(r, 0)) for r in range(model.rowCount())]
    assert "ipv4 (1)" in labels


def test_non_enum_column_has_no_completer(qtbot, ip_setup):
    """无枚举的索引列(InterfaceIndex)不挂补全器。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipIfStatsIfIndex"].completer() is None


def test_normalized_label_preview(qtbot, ip_setup):
    """选下拉 'ipv4 (1)' + 数字 5 → 规范化为枚举名,预览以 .1.5 结尾。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    dlg.set_index_value("ipIfStatsIPVersion", "ipv4 (1)")
    dlg.set_index_value("ipIfStatsIfIndex", "5")
    assert dlg.result_text().endswith(".1.5")


def test_numeric_input_preview(qtbot, ip_setup):
    """枚举列纯数字输入同样可用(数字路径)。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    dlg.set_index_value("ipIfStatsIPVersion", "1")
    dlg.set_index_value("ipIfStatsIfIndex", "5")
    assert dlg.result_text().endswith(".1.5")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ui/test_oid_builder_dialog.py::test_enum_column_has_completer -v`
Expected: FAIL — `edit.completer() is not None` 断言失败(当前未挂补全器,返回 None)。

- [ ] **Step 3: Add imports**

Edit `src/hwtransmib/ui/oid_builder_dialog.py` 的 imports:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCompleter, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)
```

- [ ] **Step 4: Attach completer for enum columns in `_build_ui`**

Edit `_build_ui` 中创建 `edit` 的循环(当前 `for spec in specs:` 块),替换为:

```python
        specs = self._row_specs()
        if specs:
            form = QFormLayout()
            for spec in specs:
                edit = QLineEdit()
                edit.setPlaceholderText(spec.syntax)
                edit.textChanged.connect(self._refresh)
                self._inputs[spec.column_name] = edit
                self._attach_completer(edit, spec)
                form.addRow(f"{spec.column_name} ({spec.syntax})", edit)
            layout.addLayout(form)
```

新增方法(在 `_row_specs` 附近):

```python
    def _attach_completer(self, edit: QLineEdit, spec) -> None:
        """对带枚举的索引列挂补全器:键入少量字符匹配枚举名。"""
        if not spec.named_values:
            return
        labels = [f"{name} ({value})" for name, value in spec.named_values]
        completer = QCompleter(labels, edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        edit.setCompleter(completer)
```

- [ ] **Step 5: Add `_normalize` and apply it in `_values`**

Edit `_values`:

```python
    def _values(self) -> dict[str, str]:
        return {name: self._normalize(name, e.text())
                for name, e in self._inputs.items()}
```

新增方法(需要按列名查 spec,故建立列名→spec 映射):

```python
    def _normalize(self, column_name: str, text: str) -> str:
        """规范化输入值。

        仅对带枚举的列生效:选中下拉项形如 'name (n)' 时取枚举名,
        交内核编码;纯数字/裸枚举名原样返回。其余列直接返回 text。
        """
        spec = self._spec_of(column_name)
        if spec is None or not spec.named_values:
            return text
        text = text.strip()
        # 形如 "name (n)" → 取括号前的枚举名
        idx = text.rfind(" (")
        if idx > 0 and text.endswith(")"):
            candidate = text[:idx]
            if any(candidate == n for n, _ in spec.named_values):
                return candidate
        return text

    def _spec_of(self, column_name: str):
        """按列名查 IndexSpec(从所属 ROW 的 index_specs)。"""
        for spec in self._row_specs():
            if spec.column_name == column_name:
                return spec
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/ui/test_oid_builder_dialog.py -v`
Expected: PASS — 4 个新用例通过;既有 3 个用例(IF-MIB ifIndex 无枚举,不挂补全器,行为不变)不回归。

- [ ] **Step 7: Run full UI + kernel suite**

Run: `uv run pytest tests/ui tests/kernel -q`
Expected: PASS。

- [ ] **Step 8: Commit**

```bash
git add src/hwtransmib/ui/oid_builder_dialog.py tests/ui/test_oid_builder_dialog.py
git commit -m "feat(ui): add TC enum completer to OID builder index inputs"
```

---

## Task 4: 全量回归与手动验收

**Files:** 无代码改动

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -q`
Expected: PASS(含翻转/新增用例,既有全部用例不回归)。

- [ ] **Step 2: Manual smoke test (optional, needs display)**

启动应用:`uv run hwtransmib`
- 导入 IP-MIB,定位到 `ipIfStatsInReceives`(OID `1.3.6.1.2.1.4.31.3.1.3`)。
- 右键「构造 OID」,确认 `ipIfStatsIPVersion` 输入框键入 `ip` 弹出候选 `ipv4 (1)`/`ipv6 (2)`。
- 选中 `ipv4 (1)`,`ipIfStatsIfIndex` 填 `5`,预览显示 `...1.3.1.3.1.5`。
- 改填纯数字 `1` 也得到同样预览。
- 确认 `ipIfStatsIfIndex`(InterfaceIndex)无候选弹出。

(无显示环境时跳过此步,自动化测试已覆盖核心行为。)

- [ ] **Step 3: Commit verification (no-op)**

若手动测试发现行为问题,定位到对应 Task 修复;否则无需提交(本任务无代码改动)。

---

## Self-Review 结果

**1. Spec coverage(逐节核对):**
- spec §3(数据提取)→ Task 1 ✓
- spec §4(校验编码放开)→ Task 2 ✓
- spec §5(UI 补全器 + 规范化)→ Task 3 ✓
- spec §6(测试策略表每行)→ 散布在 Task 1/2/3 各步骤,逐项对应:
  - named_values 提取 → Task 1 Step 1 ✓
  - 无枚举 TC 不提取 → Task 1 Step 1 ✓
  - 枚举名通过校验(翻转)→ Task 2 Step 1 ✓
  - 枚举名编码 `.1.5` → Task 2 Step 3 ✓
  - 数字仍可编码 → Task 2 Step 3 ✓
  - 非法名报错 → Task 2 Step 3 ✓
  - 非枚举列不受影响 → Task 2 Step 3 ✓
  - 补全器挂载/无补全器/规范化/纯数字 → Task 3 Step 1 ✓
- spec §7(涉及文件)→ 全部 7 个文件在 File Structure 与各 Task 覆盖 ✓
- spec §8(验收标准)→ Task 4 ✓

**2. Placeholder scan:** 无 TBD/TODO;每步含完整代码与确切命令。✓

**3. Type consistency:**
- `named_values: list[tuple[str, int]]`(Task 1 model)↔ 提取 `(str(name), int(value))`(Task 1 `_extract_named_values`)↔ UI `for name, value in spec.named_values`(Task 3)一致 ✓
- `_is_enum_name`、`_coerce`、`_validate_value`(Task 2)↔ 测试调用一致 ✓
- `_attach_completer`、`_normalize`、`_spec_of`、`_values`(Task 3)命名前后一致 ✓
- `_row_specs()` 既有方法被 `_spec_of` 复用,返回 `IndexSpec`(含 `named_values`)✓

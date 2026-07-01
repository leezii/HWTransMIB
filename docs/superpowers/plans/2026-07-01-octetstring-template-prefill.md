# OctetString 模板预填 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构造表列 OID 时,对字符串类索引列(OctetString/IpAddress/PhysAddress 等)按列 OID 精确匹配,从 `~/.hwtransmib/templates.json` 预填纯文本模板,用户稍作修改即可。

**Architecture:** 新增无 Qt 依赖的内核模块 `StringTemplateStore`(读 JSON → 内存 dict → 按 OID 查)。UI 层在打开 OID 构造对话框时,对字符串类索引列(非整数、非枚举)查模板,命中则预填到 QLineEdit。模板文件是外部只读资源,由其他程序生成后放入目录生效。

**Tech Stack:** Python 3.11+ stdlib (`json`, `pathlib`), PySide6 (仅 UI 集成), pytest + pytest-qt (测试)

**规格文件:** `docs/superpowers/specs/2026-07-01-octetstring-template-prefill-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `src/hwtransmib/kernel/string_templates.py` | 按 OID 查预填模板;读 JSON、容错、内存查询 | 新增 |
| `tests/kernel/test_string_templates.py` | StringTemplateStore 单元测试 | 新增 |
| `src/hwtransmib/persistence/user_data.py` | 暴露 `base_dir` 属性 | 修改 |
| `src/hwtransmib/ui/oid_builder_dialog.py` | 新增 `templates` 参数,字符串类列预填 | 修改 |
| `src/hwtransmib/ui/main_window.py` | 创建/持有 StringTemplateStore,传给对话框 | 修改 |
| `tests/ui/test_oid_builder_dialog.py` | 字符串类列预填测试 | 修改 |

依赖链:UserData.base_dir → MainWindow 创建 StringTemplateStore → OidBuilderDialog 使用 → 字符串类列 lookup 预填。三层改动按依赖顺序自底向上。

---

## Task 1: StringTemplateStore 内核模块(TDD)

**Files:**
- Create: `src/hwtransmib/kernel/string_templates.py`
- Test: `tests/kernel/test_string_templates.py`

- [ ] **Step 1: 写失败测试 — 正常加载 + lookup 命中/未命中**

Create `tests/kernel/test_string_templates.py`:

```python
"""StringTemplateStore 测试:按列 OID 精确查预填模板。

容错优先:文件缺失/损坏/某条缺字段都不崩溃,返回空表或跳过该条。
"""
import json

from hwtransmib.kernel.string_templates import StringTemplateStore


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_lookup_hit(tmp_path):
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.3.6.1.2.1.4.22.1.3", "template": "192.168.1.1"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.3.6.1.2.1.4.22.1.3") == "192.168.1.1"


def test_lookup_miss(tmp_path):
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.3.6.1.2.1.4.22.1.3", "template": "192.168.1.1"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("9.9.9") is None


def test_lookup_miss_when_empty(tmp_path):
    """未 reload 前查询命中 None(构造后内存表为空)。"""
    store = StringTemplateStore(tmp_path / "templates.json")
    assert store.lookup("1.1") is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/kernel/test_string_templates.py -v`
Expected: FAIL,ModuleNotFoundError: No module named 'hwtransmib.kernel.string_templates'

- [ ] **Step 3: 实现最小 StringTemplateStore(仅 lookup 命中/未命中)**

Create `src/hwtransmib/kernel/string_templates.py`:

```python
"""OctetString 预填模板存储:按列 OID 精确查模板。

模板来自外部资源文件(~/.hwtransmib/templates.json),由其他程序生成后
放入目录生效,程序只读不改。文件缺失/损坏均不抛异常,返回空表。
"""
from __future__ import annotations

import json
from pathlib import Path


class StringTemplateStore:
    """按列 OID 精确查预填模板。"""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._table: dict[str, str] = {}

    def reload(self) -> None:
        """重新读盘构建内存表。文件不存在/损坏 → 空表(不抛异常)。"""
        self._table = {}
        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        for entry in data.get("templates", []):
            oid = entry.get("oid")
            template = entry.get("template")
            # 缺 oid 或 template 字段 → 跳过该条
            if not isinstance(oid, str) or not isinstance(template, str):
                continue
            self._table[oid] = template

    def lookup(self, oid: str) -> str | None:
        """按列 OID 精确查模板;未命中返回 None。"""
        return self._table.get(oid)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/kernel/test_string_templates.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/hwtransmib/kernel/string_templates.py tests/kernel/test_string_templates.py
git commit -m "feat(kernel): StringTemplateStore for OctetString prefill templates"
```

---

## Task 2: StringTemplateStore 容错与边界(TDD)

**Files:**
- Test: `tests/kernel/test_string_templates.py`

- [ ] **Step 1: 追加失败测试 — 文件缺失/JSON 损坏/缺字段/重复 OID/reload 刷新**

在 `tests/kernel/test_string_templates.py` 末尾追加:

```python
def test_missing_file_yields_empty(tmp_path):
    """文件不存在 → 空表,所有 lookup 返回 None,不抛异常。"""
    store = StringTemplateStore(tmp_path / "nope.json")
    store.reload()
    assert store.lookup("1.1") is None


def test_corrupt_json_yields_empty(tmp_path):
    """JSON 非法 → 空表,不崩溃。"""
    f = tmp_path / "templates.json"
    f.write_text("{not valid json", encoding="utf-8")
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") is None


def test_entry_missing_oid_skipped(tmp_path):
    """某条缺 oid → 跳过该条,其余正常加载。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"template": "no-oid-here"},  # 缺 oid,跳过
        {"oid": "1.2", "template": "ok"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.2") == "ok"
    assert store.lookup("no-oid-here") is None


def test_entry_missing_template_skipped(tmp_path):
    """某条缺 template → 跳过该条。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.1"},  # 缺 template,跳过
        {"oid": "1.2", "template": "ok"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") is None
    assert store.lookup("1.2") == "ok"


def test_duplicate_oid_last_wins(tmp_path):
    """重复 OID:数组中后出现的覆盖先出现的。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.1", "template": "first"},
        {"oid": "1.1", "template": "second"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") == "second"


def test_reload_refreshes(tmp_path):
    """reload() 重新读盘:文件中途替换后刷新内存表。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [{"oid": "1.1", "template": "old"}]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") == "old"
    # 替换文件内容
    _write(f, {"templates": [{"oid": "1.1", "template": "new"}]})
    store.reload()
    assert store.lookup("1.1") == "new"


def test_comment_field_ignored(tmp_path):
    """comment 字段不影响匹配/预填(纯标注,程序不使用)。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.1", "template": "tpl", "comment": "just a note"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") == "tpl"
```

- [ ] **Step 2: 运行测试确认全部通过**

Run: `uv run pytest tests/kernel/test_string_templates.py -v`
Expected: 10 passed(3 原有 + 7 新增)。Task 1 的实现已覆盖这些场景,无需改实现代码。

- [ ] **Step 3: 提交**

```bash
git add tests/kernel/test_string_templates.py
git commit -m "test(kernel): StringTemplateStore edge cases (corrupt/skip/dup/reload)"
```

---

## Task 3: UserData 暴露 base_dir

**Files:**
- Modify: `src/hwtransmib/persistence/user_data.py:19-22`
- Test: `tests/persistence/test_user_data.py`

- [ ] **Step 1: 写失败测试 — base_dir 属性可读**

在 `tests/persistence/test_user_data.py` 末尾追加:

```python
def test_base_dir_property_exposed(tmp_path):
    """UserData.base_dir 返回构造时传入的目录路径。"""
    ud = UserData(base_dir=tmp_path)
    assert ud.base_dir == tmp_path
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/persistence/test_user_data.py::test_base_dir_property_exposed -v`
Expected: FAIL,AttributeError: 'UserData' object has no attribute 'base_dir'

- [ ] **Step 3: 暴露 base_dir 属性**

Modify `src/hwtransmib/persistence/user_data.py`。在 `__init__` 内 `self._base = ...` 已存在(line 21),改为:

```python
    def __init__(self, base_dir: Path | None = None,
                 history_limit: int = _DEFAULT_HISTORY_LIMIT) -> None:
        self._base = Path(base_dir) if base_dir else Path.home() / ".hwtransmib"
        self._limit = history_limit
```

然后在 `set_config` 方法之前(即 `# --- config ---` 注释之前)插入 property:

```python
    @property
    def base_dir(self) -> Path:
        """用户数据目录(~/.hwtransmib)。供外部拼资源路径,如模板文件。"""
        return self._base

    # --- config ---
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/persistence/test_user_data.py -v`
Expected: 所有测试通过(含新增 test_base_dir_property_exposed)

- [ ] **Step 5: 提交**

```bash
git add src/hwtransmib/persistence/user_data.py tests/persistence/test_user_data.py
git commit -m "feat(persistence): expose UserData.base_dir property"
```

---

## Task 4: OidBuilderDialog 接受并使用模板

**Files:**
- Modify: `src/hwtransmib/ui/oid_builder_dialog.py:22-49`
- Test: `tests/ui/test_oid_builder_dialog.py`

本任务先加构造参数 + 字符串类列预填逻辑,UI 测试验证。`MainWindow` 的装配在 Task 5 完成,所以本任务的 UI 测试直接构造 StringTemplateStore 传入。

- [ ] **Step 1: 写失败测试 — 字符串类列命中模板则预填,整数/枚举列不预填**

在 `tests/ui/test_oid_builder_dialog.py` 顶部 import 区追加:

```python
import json

from hwtransmib.kernel.string_templates import StringTemplateStore
```

然后在文件末尾追加测试:

```python
@pytest.fixture
def ip_setup_with_templates(fixtures_mibs_dir, tmp_path):
    """IP-MIB + 一个含 IpAddress 列模板的 StringTemplateStore。

    ipNetToMediaNetAddress(OID 1.3.6.1.2.1.4.22.1.3,IpAddress 类型)是字符串类
    索引列;ipNetToMediaIfIndex(Integer32)是整数列。模板只对前者生效。
    """
    from pathlib import Path
    ip_mib = Path("src/hwtransmib/kernel/standard_mibs/IP-MIB")
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir),
                                      "src/hwtransmib/kernel/standard_mibs"])
    imp.import_files([str(ip_mib)])
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    # 预置模板:IpAddress 列(字符串类)有模板,整数列无
    tpl_file = tmp_path / "templates.json"
    tpl_file.write_text(json.dumps({"templates": [
        {"oid": "1.3.6.1.2.1.4.22.1.3", "template": "192.168.1.100"},
    ]}, ensure_ascii=False), encoding="utf-8")
    store = StringTemplateStore(tpl_file)
    store.reload()
    return svc, imp.get_root(), store


def test_string_column_prefilled_from_template(qtbot, ip_setup_with_templates):
    """字符串类索引列(IpAddress)命中模板 → 预填到输入框。"""
    svc, root, store = ip_setup_with_templates
    node = root.find("1.3.6.1.2.1.4.22.1.2")  # ipNetToMediaPhysAddress COLUMN
    dlg = OidBuilderDialog(node, svc, templates=store)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipNetToMediaNetAddress"].text() == "192.168.1.100"


def test_integer_column_not_prefilled(qtbot, ip_setup_with_templates):
    """整数列(Integer32)即使无模板也不预填(本就不查模板),保持空。"""
    svc, root, store = ip_setup_with_templates
    node = root.find("1.3.6.1.2.1.4.22.1.2")
    dlg = OidBuilderDialog(node, svc, templates=store)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipNetToMediaIfIndex"].text() == ""


def test_string_column_empty_when_no_template(qtbot, fixtures_mibs_dir, tmp_path):
    """字符串类列未命中模板 → 留空(与现状一致)。"""
    from pathlib import Path
    ip_mib = Path("src/hwtransmib/kernel/standard_mibs/IP-MIB")
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir),
                                      "src/hwtransmib/kernel/standard_mibs"])
    imp.import_files([str(ip_mib)])
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    # 空模板表(不 reload,内存表为空,所有 lookup 返回 None)
    store = StringTemplateStore(tmp_path / "templates.json")
    root = imp.get_root()
    node = root.find("1.3.6.1.2.1.4.22.1.2")
    dlg = OidBuilderDialog(node, svc, templates=store)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipNetToMediaNetAddress"].text() == ""
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest tests/ui/test_oid_builder_dialog.py::test_string_column_prefilled_from_template -v`
Expected: FAIL,TypeError: OidBuilderDialog.__init__() got an unexpected keyword argument 'templates'

- [ ] **Step 3: 给 OidBuilderDialog 加 templates 参数 + 预填逻辑**

Modify `src/hwtransmib/ui/oid_builder_dialog.py`。

(a) import 区追加(line 14 之后):

```python
from hwtransmib.kernel.string_templates import StringTemplateStore
```

(b) `__init__` 签名与赋值改为(templates 可选,默认 None,保证向后兼容):

```python
    def __init__(self, node: MibNode, service: OidBuildService,
                 templates: StringTemplateStore | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._node = node
        self._service = service
        self._templates = templates
        self._inputs: dict[str, QLineEdit] = {}
        self.setWindowTitle(f"构造 OID — {node.name}")
        self.setMinimumWidth(420)
        self._build_ui()
        self._refresh()
```

(c) 在 `_build_ui` 中,`self._inputs[spec.column_name] = edit` 之后、`self._attach_completer(edit, spec)` 之后(line 48-49 附近),追加预填逻辑。把这段:

```python
                edit.textChanged.connect(self._refresh)
                self._inputs[spec.column_name] = edit
                self._attach_completer(edit, spec)
                form.addRow(f"{spec.column_name} ({spec.syntax})", edit)
```

改为:

```python
                edit.textChanged.connect(self._refresh)
                self._inputs[spec.column_name] = edit
                self._attach_completer(edit, spec)
                self._prefill_template(spec, edit)
                form.addRow(f"{spec.column_name} ({spec.syntax})", edit)
```

(d) 新增 `_prefill_template` 方法(放在 `_attach_completer` 方法之后):

```python
    def _prefill_template(self, spec, edit: QLineEdit) -> None:
        """字符串类索引列(非整数、非枚举)查模板预填;命中则 setText。

        预填用 setText 会触发 textChanged → _refresh,对话框打开即显示
        编码后的 OID 预览。仅在 _build_ui 构造时执行一次,之后不覆盖用户编辑。
        """
        if self._templates is None:
            return
        # 仅字符串类列查模板:非整数、非枚举
        if spec.is_integer or spec.named_values:
            return
        if not spec.column_oid:
            return
        template = self._templates.lookup(spec.column_oid)
        if template:
            edit.setText(template)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run pytest tests/ui/test_oid_builder_dialog.py -v`
Expected: 所有测试通过(含 3 个新增预填测试)。注意:`templates` 设为可选参数,原有测试 `OidBuilderDialog(node, svc)` 不传 templates 仍正常工作。

- [ ] **Step 5: 提交**

```bash
git add src/hwtransmib/ui/oid_builder_dialog.py tests/ui/test_oid_builder_dialog.py
git commit -m "feat(ui): prefill string-type index columns from templates"
```

---

## Task 5: MainWindow 装配 StringTemplateStore

**Files:**
- Modify: `src/hwtransmib/ui/main_window.py:64, 159-162, 323-325, 402`

- [ ] **Step 1: import StringTemplateStore**

Modify `src/hwtransmib/ui/main_window.py`。在 import 区(line 24 附近,`from hwtransmib.persistence.user_data import UserData` 之后)追加:

```python
from hwtransmib.kernel.string_templates import StringTemplateStore
```

- [ ] **Step 2: 添加 _templates 实例属性初始化**

把 `__init__` 中的(line 64):

```python
        self._oid_svc: OidBuildService | None = None
```

改为:

```python
        self._oid_svc: OidBuildService | None = None
        self._templates: StringTemplateStore | None = None
```

- [ ] **Step 3: 第一处装配点 — _on_import(line 159 附近)**

把:

```python
            self._oid_svc = OidBuildService(
                parser=self._import.get_parser(), root=root,
                user_data=self._ud,
            )
```

改为:

```python
            self._oid_svc = OidBuildService(
                parser=self._import.get_parser(), root=root,
                user_data=self._ud,
            )
            self._templates = StringTemplateStore(
                self._ud.base_dir / "templates.json"
            )
            self._templates.reload()
```

- [ ] **Step 4: 第二处装配点 — _reload_last(line 323 附近)**

把:

```python
        self._oid_svc = OidBuildService(
            parser=self._import.get_parser(), root=root, user_data=self._ud
        )
```

改为:

```python
        self._oid_svc = OidBuildService(
            parser=self._import.get_parser(), root=root, user_data=self._ud
        )
        self._templates = StringTemplateStore(
            self._ud.base_dir / "templates.json"
        )
        self._templates.reload()
```

- [ ] **Step 5: _open_builder 传 templates 给对话框(line 402)**

把:

```python
        dlg = OidBuilderDialog(node, self._oid_svc, self)
```

改为:

```python
        dlg = OidBuilderDialog(node, self._oid_svc, self._templates, self)
```

- [ ] **Step 6: 运行全量测试确认无回归**

Run: `uv run pytest -x`
Expected: 全部通过。无新测试需要写——装配改动由现有 main_window_state 测试与 oid_builder_dialog 测试覆盖(它们走真实装配路径或直接构造)。

- [ ] **Step 7: 提交**

```bash
git add src/hwtransmib/ui/main_window.py
git commit -m "feat(ui): wire StringTemplateStore into MainWindow OID builder"
```

---

## Task 6: 全量验证与文档

- [ ] **Step 1: 运行全量测试 + 内核覆盖率**

Run: `uv run pytest --cov=hwtransmib.kernel --cov-report=term`
Expected: 全部通过;`string_templates.py` 覆盖率 100%(所有分支:命中/未命中/缺失/损坏/跳过/重复/reload 均有测试)。

- [ ] **Step 2: 手动冒烟验证(可选,需 GUI 环境)**

创建测试模板文件 `~/.hwtransmib/templates.json`:

```json
{
  "templates": [
    {
      "oid": "1.3.6.1.2.1.4.22.1.3",
      "template": "192.168.1.100",
      "comment": "ipNetToMediaNetAddress 默认 IP 模板"
    }
  ]
}
```

Run: `uv run hwtransmib`,导入 IP-MIB,定位到 `ipNetToMediaPhysAddress` 列,打开构造 OID 对话框 → ipNetToMediaNetAddress 输入框应预填 `192.168.1.100`,预览区显示编码后的 OID。

- [ ] **Step 3: 完成(无需提交,无文件改动)**

本步骤为验证,不产生文件变更。如 Step 2 创建了 `~/.hwtransmib/templates.json`,按需清理。

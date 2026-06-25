# HWTransMIB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个跨平台 Python 桌面应用,导入 SNMP MIB 文件,以树形结构浏览,查看节点属性,搜索节点,对选中的标量/表列节点交互式构造完整 OID 访问字符串。

**Architecture:** 四层单向依赖(UI → 服务 → 内核 → 持久化)。MIB 内核层是纯 Python(无 Qt 依赖),封装 PySnmp 7.1 的 MibBuilder/MibViewController。OID 构造复用 PySnmp 原生的 `getInstIdFromIndices` 索引编码能力,避免重写 SNMP 编码规则。

**Tech Stack:** Python ≥3.10、uv(环境管理)、PySide6(UI)、pysnmp + pysmi(MIB 解析)、pytest + pytest-qt(测试)、PyInstaller(打包)。

**参考规格:** `docs/superpowers/specs/2026-06-25-mib-explorer-design.md`

---

## 文件结构

```
HWTransMIB/
├── pyproject.toml                      # uv 项目配置 + 依赖
├── src/hwtransmib/
│   ├── __init__.py
│   ├── kernel/                         # MIB 内核层(纯 Python, 无 Qt)
│   │   ├── __init__.py
│   │   ├── model.py                    # MibNode / NodeType / IndexSpec dataclass
│   │   ├── mib_parser.py               # MibParser(封装 PySnmp MibBuilder)
│   │   ├── tree_builder.py             # MibTreeBuilder(MibTree 构建 + 节点类型推断)
│   │   ├── oid_builder.py              # OidBuilder(SNMP 索引编码,封装 getInstIdFromIndices)
│   │   ├── search_index.py             # SearchIndex(名称哈希 + OID 前缀索引)
│   │   └── standard_mibs/              # 内置标准 MIB 资源目录
│   │       └── *.mib
│   ├── services/                       # 应用服务层
│   │   ├── __init__.py
│   │   ├── import_service.py           # ImportService(导入编排 + 进度)
│   │   ├── search_service.py           # SearchService(200ms 防抖搜索)
│   │   └── oid_build_service.py        # OidBuildService(COLUMN→构造OID + 历史)
│   ├── persistence/                    # 持久化层
│   │   ├── __init__.py
│   │   └── json_store.py               # JsonStore(原子写入, config/imports/favorites/history)
│   └── ui/                             # UI 层(PySide6)
│       ├── __init__.py
│       ├── app.py                      # QApplication 入口
│       ├── main_window.py              # MainWindow(三栏 + 工具栏 + 状态栏)
│       ├── mib_tree_model.py           # MibTreeModel(QAbstractItemModel)
│       ├── mib_tree_view.py            # MibTreeView(树视图 + 右键菜单)
│       ├── property_panel.py           # PropertyPanel(键值对表格)
│       ├── detail_dock.py              # DetailDock(可折叠详情区, 含 3 个 Tab)
│       ├── oid_builder_dialog.py       # OidBuilderDialog(构造表单 + 实时预览)
│       └── search_box.py               # SearchBox(防抖搜索 + 结果跳转)
├── tests/
│   ├── conftest.py                     # 共享 fixture(测试用 MIB 文件、临时目录)
│   ├── kernel/
│   │   ├── test_model.py
│   │   ├── test_mib_parser.py
│   │   ├── test_tree_builder.py
│   │   ├── test_oid_builder.py
│   │   └── test_search_index.py
│   ├── services/
│   │   ├── test_import_service.py
│   │   ├── test_search_service.py
│   │   └── test_oid_build_service.py
│   ├── persistence/
│   │   └── test_json_store.py
│   └── ui/
│       └── test_oid_builder_dialog.py
└── tests/fixtures/mibs/                # 测试用真实 MIB 文件
    └── IF-MIB.txt                      # 从 mibs.pysnmp.com 获取
```

**文件职责边界:**
- `kernel/` 每个文件单一职责,可脱离 GUI 测试。`oid_builder.py` 是核心难点。
- `services/` 编排流程,是 UI 与内核的缓冲。UI 不直接 import kernel 的 PySnmp 封装。
- `ui/` 视图组件,通过服务层访问数据。

---

## 阶段 0:项目脚手架

### Task 0.1: uv 项目初始化与依赖配置

**Files:**
- Create: `pyproject.toml`
- Create: `src/hwtransmib/__init__.py`

- [ ] **Step 1: 初始化 uv 项目并创建包结构**

```bash
cd /Users/zhili/Develop/python/HWTransMIB
uv init --lib --python 3.11 .
mkdir -p src/hwtransmib/kernel src/hwtransmib/services src/hwtransmib/persistence src/hwtransmib/ui
mkdir -p tests/kernel tests/services tests/persistence tests/ui tests/fixtures/mibs
```

- [ ] **Step 2: 编写 pyproject.toml**

将 `pyproject.toml` 替换为以下完整内容(覆盖 uv init 生成的默认):

```toml
[project]
name = "hwtransmib"
version = "0.1.0"
description = "SNMP MIB 浏览与 OID 构造工具"
requires-python = ">=3.10"
dependencies = [
    "pysnmp>=4.5,<5",
    "pysmi>=1.5,<2",
    "PySide6>=6.6,<7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.4",
    "pytest-cov>=5.0",
]

[project.scripts]
hwtransmib = "hwtransmib.ui.app:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/hwtransmib"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra"
qt_api = "pyside6"
```

- [ ] **Step 3: 安装依赖**

```bash
uv sync --extra dev
```
Expected: 成功创建 `.venv/` 并安装所有依赖(首次会下载 PySide6,需联网)。

- [ ] **Step 4: 验证 PySnmp 可用**

```bash
uv run python -c "from pysnmp.smi import builder, view, compiler; print('pysnmp ok')"
```
Expected: 输出 `pysnmp ok`。

- [ ] **Step 5: 创建包 __init__ 占位**

为所有包创建空 `__init__.py`:

```bash
for d in kernel services persistence ui; do touch src/hwtransmib/$d/__init__.py; done
touch tests/__init__.py
```

- [ ] **Step 6: 验证可运行空测试**

创建 `tests/test_smoke.py`:

```python
def test_smoke():
    assert 1 + 1 == 2
```

运行:`uv run pytest tests/test_smoke.py -v`
Expected: PASS。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold project with uv, pysnmp, PySide6 deps"
```

### Task 0.2: 准备测试用真实 MIB 文件

**Files:**
- Create: `tests/fixtures/mibs/IF-MIB`
- Create: `tests/fixtures/mibs/SNMPv2-SMI`
- Create: `tests/fixtures/mibs/SNMPv2-TC`
- Create: `tests/conftest.py`

- [ ] **Step 1: 下载测试用标准 MIB 文件**

这些是公开标准 MIB,用于测试解析与构造:

```bash
cd /Users/zhili/Develop/python/HWTransMIB/tests/fixtures/mibs
curl -fsSL -o SNMPv2-SMI https://raw.githubusercontent.com/lextudio/pysnmp/master/pysnmp/smi/mibs/SNMPv2-SMI
curl -fsSL -o SNMPv2-TC https://raw.githubusercontent.com/lextudio/pysnmp/master/pysnmp/smi/mibs/SNMPv2-TC
curl -fsSL -o SNMPv2-MIB https://raw.githubusercontent.com/lextudio/pysnmp/master/pysnmp/smi/mibs/SNMPv2-MIB
curl -fsSL -o IF-MIB https://raw.githubusercontent.com/lextudio/pysnmp/master/pysnmp/smi/mibs/IF-MIB
```
Expected: 4 个文件下载成功。若某个 URL 失败,改从 `https://mibs.pysnmp.com/asn1/<NAME>` 下载。

- [ ] **Step 2: 验证文件可被 PySnmp 解析**

```bash
cd /Users/zhili/Develop/python/HWTransMIB
uv run python -c "
from pysnmp.smi import builder, view, compiler
b = builder.MibBuilder()
compiler.add_mib_compiler(b, sources=['file://$(pwd)/tests/fixtures/mibs'])
b.load_modules('IF-MIB')
v = view.MibViewController(b)
oid, label, suffix = v.get_node_name((1,3,6,1,2,1,2,2,1,2))
print('ifDescr OID:', '.'.join(map(str,oid)))
"
```
Expected: 输出 `ifDescr OID: 1.3.6.1.2.1.2.2.1.2`。

- [ ] **Step 3: 编写 conftest.py 共享 fixture**

```python
# tests/conftest.py
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_mibs_dir() -> Path:
    """测试用真实 MIB 文件目录。"""
    return Path(__file__).parent / "fixtures" / "mibs"


@pytest.fixture(scope="session")
def if_mib_path(fixtures_mibs_dir: Path) -> Path:
    return fixtures_mibs_dir / "IF-MIB"
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: add real MIB fixtures (IF-MIB, SNMPv2-*) and conftest"
```

---

## 阶段 1:内核层 — 领域模型

### Task 1.1: MibNode / NodeType / IndexSpec 数据模型

**Files:**
- Create: `src/hwtransmib/kernel/model.py`
- Test: `tests/kernel/test_model.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/kernel/test_model.py
from hwtransmib.kernel.model import IndexSpec, MibNode, NodeType


def test_node_type_values():
    assert NodeType.SCALAR.value == "scalar"
    assert NodeType.COLUMN.value == "column"
    assert NodeType.TABLE.value == "table"
    assert NodeType.ROW.value == "row"


def test_is_constructible_scalar():
    node = MibNode(oid="1.3.6.1.2.1.1.1", name="sysDescr", node_type=NodeType.SCALAR)
    assert node.is_constructible is True


def test_is_constructible_column():
    node = MibNode(oid="1.3.6.1.2.1.2.2.1.2", name="ifDescr", node_type=NodeType.COLUMN)
    assert node.is_constructible is True


def test_not_constructible_table():
    node = MibNode(oid="1.3.6.1.2.1.2.2", name="ifTable", node_type=NodeType.TABLE)
    assert node.is_constructible is False


def test_child_relationship():
    root = MibNode(oid="1.3", name="org", node_type=NodeType.SUBTREE)
    child = MibNode(oid="1.3.6", name="dod", node_type=NodeType.SUBTREE, parent=root)
    root.children.append(child)
    assert child.parent is root
    assert root.children == [child]


def test_full_name_path():
    root = MibNode(oid="1.3.6.1.2.1.2.2.1", name="ifEntry", node_type=NodeType.ROW)
    leaf = MibNode(oid="1.3.6.1.2.1.2.2.1.2", name="ifDescr",
                   node_type=NodeType.COLUMN, parent=root)
    root.children.append(leaf)
    assert leaf.name_path == ["ifEntry", "ifDescr"]


def test_index_spec_defaults():
    spec = IndexSpec(column_name="ifIndex", column_oid="1.3.6.1.2.1.2.2.1.1",
                     implied=False, syntax="INTEGER")
    assert spec.implied is False
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/kernel/test_model.py -v`
Expected: FAIL(ImportError — 模块不存在)。

- [ ] **Step 3: 实现 model.py**

```python
# src/hwtransmib/kernel/model.py
"""MIB 内核领域模型。纯 dataclass,无 Qt 依赖。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    MODULE = "module"        # 📦 MIB 模块根
    SUBTREE = "subtree"      # 📁 中间子树节点
    SCALAR = "scalar"        # 🟢 标量(0 索引, OID 固定)
    TABLE = "table"          # 🔴 表对象
    ROW = "row"              # 🔴 表行(entry)
    COLUMN = "column"        # 🟢 表列对象(可构造)


@dataclass
class IndexSpec:
    """表的索引列定义。"""
    column_name: str
    column_oid: str
    implied: bool
    syntax: str


@dataclass
class MibNode:
    """MIB 树中的一个节点。解析完成后视为只读快照。"""
    oid: str
    name: str
    node_type: NodeType
    syntax: str | None = None
    access: str | None = None
    status: str | None = None
    description: str | None = None
    units: str | None = None
    parent: MibNode | None = None
    children: list[MibNode] = field(default_factory=list)
    module_name: str | None = None
    # 仅 TABLE/ROW 节点相关:该表的索引列定义
    index_specs: list[IndexSpec] | None = None

    @property
    def is_constructible(self) -> bool:
        """该节点是否可构造 OID(标量或表列对象)。"""
        return self.node_type in (NodeType.SCALAR, NodeType.COLUMN)

    @property
    def name_path(self) -> list[str]:
        """从该节点到最近命名祖先的名称路径(用于显示如 ifEntry.ifDescr)。"""
        path: list[str] = []
        node: MibNode | None = self
        while node is not None:
            path.append(node.name)
            node = node.parent
        path.reverse()
        return path
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/kernel/test_model.py -v`
Expected: 7 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(kernel): add MibNode/NodeType/IndexSpec domain model"
```

---

## 阶段 2:内核层 — MIB 解析器

### Task 2.1: MibParser 封装 PySnmp

**Files:**
- Create: `src/hwtransmib/kernel/mib_parser.py`
- Test: `tests/kernel/test_mib_parser.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/kernel/test_mib_parser.py
import pytest

from hwtransmib.kernel.mib_parser import MibParser, MibParseError, ParseResult


@pytest.fixture
def parser(fixtures_mibs_dir):
    return MibParser(extra_sources=[str(fixtures_mibs_dir)])


def test_parse_single_mib(parser):
    result = parser.parse(["IF-MIB"])
    assert isinstance(result, ParseResult)
    assert "IF-MIB" in result.loaded_modules
    assert len(result.errors) == 0


def test_get_node_oid_by_name(parser):
    parser.parse(["IF-MIB"])
    oid = parser.get_oid_by_name("ifDescr")
    assert oid == "1.3.6.1.2.1.2.2.1.2"


def test_get_node_oid_missing_module_raises(parser):
    # 未 parse 时查询应报错
    with pytest.raises(MibParseError):
        parser.get_oid_by_name("ifDescr")


def test_parse_missing_module_reports_error(parser):
    result = parser.parse(["NONEXISTENT-MIB-XYZ"])
    assert "IF-MIB" not in result.loaded_modules
    assert any("NONEXISTENT-MIB-XYZ" in str(e) for e in result.errors)


def test_has_view(parser):
    parser.parse(["IF-MIB"])
    assert parser.is_loaded("IF-MIB")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/kernel/test_mib_parser.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 mib_parser.py**

```python
# src/hwtransmib/kernel/mib_parser.py
"""封装 PySnmp MibBuilder/MibViewController,提供 MIB 解析与查询能力。"""
from __future__ import annotations

from dataclasses import dataclass, field

from pysnmp.smi import builder, compiler, error, view


class MibParseError(Exception):
    """MIB 解析相关错误。"""


@dataclass
class ParseResult:
    """一次解析的结果。"""
    loaded_modules: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MibParser:
    """封装 PySnmp 的 MIB 加载与查询。

    extra_sources: 额外的 MIB 文件目录(含标准库 + 用户目录)。
    """

    def __init__(self, extra_sources: list[str] | None = None) -> None:
        self._builder = builder.MibBuilder()
        sources = [f"file://{p}" for p in (extra_sources or [])]
        sources.append("https://mibs.pysnmp.com/asn1/@mib@")
        compiler.add_mib_compiler(self._builder, sources=sources)
        self._view: view.MibViewController | None = None
        self._loaded: set[str] = set()

    def parse(self, module_names: list[str]) -> ParseResult:
        """加载给定 MIB 模块(自动按依赖顺序补齐)。部分失败不中断。"""
        result = ParseResult()
        for name in module_names:
            try:
                self._builder.load_modules(name)
                self._loaded.add(name)
                result.loaded_modules.append(name)
            except error.MibNotFoundError as exc:
                result.errors.append(f"模块 {name} 未找到(可能依赖缺失): {exc}")
            except error.SmiError as exc:
                result.errors.append(f"模块 {name} 解析失败: {exc}")
        if self._loaded:
            self._view = view.MibViewController(self._builder)
        return result

    def is_loaded(self, module_name: str) -> bool:
        return module_name in self._loaded

    @property
    def view(self) -> view.MibViewController:
        if self._view is None:
            raise MibParseError("尚未加载任何 MIB 模块")
        return self._view

    def get_oid_by_name(self, name: str, module: str | None = None) -> str:
        """根据节点名查询完整 OID。"""
        try:
            label = (module,) + (name,) if module else (name,)
            oid, _, _ = self.view.get_node_name(label)
        except error.SmiError as exc:
            raise MibParseError(f"找不到节点 {name}: {exc}") from exc
        return ".".join(map(str, oid))
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/kernel/test_mib_parser.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(kernel): add MibParser wrapping PySnmp MibBuilder"
```

---

## 阶段 3:内核层 — 树构建器

### Task 3.1: MibTreeBuilder 构建 OID 树 + 节点类型推断

**Files:**
- Create: `src/hwtransmib/kernel/tree_builder.py`
- Test: `tests/kernel/test_tree_builder.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/kernel/test_tree_builder.py
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def root(fixtures_mibs_dir):
    parser = MibParser(extra_sources=[str(fixtures_mibs_dir)])
    parser.parse(["IF-MIB"])
    return MibTreeBuilder(parser).build()


def test_build_returns_root(root: MibNode):
    assert root.oid == "1.3"
    assert root.name == "org"


def test_find_node_by_oid(root: MibNode):
    node = root.find("1.3.6.1.2.1.2.2.1.2")
    assert node is not None
    assert node.name == "ifDescr"
    assert node.node_type == NodeType.COLUMN


def test_if_table_is_table_type(root: MibNode):
    node = root.find("1.3.6.1.2.1.2.2")
    assert node is not None
    assert node.node_type == NodeType.TABLE


def test_if_entry_has_index_specs(root: MibNode):
    entry = root.find("1.3.6.1.2.1.2.2.1")
    assert entry is not None
    assert entry.index_specs is not None
    assert entry.index_specs[0].column_name == "ifIndex"
    assert entry.index_specs[0].syntax == "INTEGER"


def test_scalar_node_type(root: MibNode):
    node = root.find("1.3.6.1.2.1.1.1") or root.find("1.3.6.1.2.1.2.1")
    assert node is not None
    assert node.node_type == NodeType.SCALAR


def test_find_nonexistent_returns_none(root: MibNode):
    assert root.find("9.9.9.9") is None
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/kernel/test_tree_builder.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 tree_builder.py**

```python
# src/hwtransmib/kernel/tree_builder.py
"""从 MibParser 构建 OID 驱动的 MibNode 树,推断节点类型与索引定义。"""
from __future__ import annotations

from pysnmp.smi import error
from pysnmp.smi.info import ObjectTypeMacro, TableToRow  # noqa: F401  类型探测辅助

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import IndexSpec, MibNode, NodeType


class MibTreeBuilder:
    """遍历 MibParser 已加载的所有节点,构建 OID 层级树。"""

    def __init__(self, parser: MibParser) -> None:
        self._parser = parser

    def build(self) -> MibNode:
        """返回 OID 树根节点(1.3 / org)。"""
        root = MibNode(oid="1.3", name="org", node_type=NodeType.SUBTREE)
        view = self._parser.view

        # 遍历所有已加载节点
        try:
            oid, label, _ = view.get_first_node_name()
        except error.SmiError:
            return root

        node_cache: dict[str, MibNode] = {root.oid: root}
        while True:
            try:
                self._add_node(oid, label, root, node_cache)
                oid, label, _ = view.get_next_node_name(oid)
            except error.NoSuchObjectError:
                break
            except error.SmiError:
                break
        return root

    def _add_node(self, oid: tuple[int, ...], label: tuple[str, ...],
                  root: MibNode, cache: dict[str, MibNode]) -> None:
        oid_str = ".".join(map(str, oid))
        if oid_str in cache or not oid_str.startswith(root.oid):
            return

        name = label[-1] if label else oid_str
        module, sym, _ = self._safe_location(label)
        node_type, syntax, access, status, desc, units, index_specs = self._probe(
            module, sym, oid
        )

        parent_oid = ".".join(map(str, oid[:-1])) if len(oid) > 1 else root.oid
        parent = cache.get(parent_oid, root)
        node = MibNode(
            oid=oid_str, name=name, node_type=node_type, syntax=syntax,
            access=access, status=status, description=desc, units=units,
            parent=parent, module_name=module, index_specs=index_specs,
        )
        parent.children.append(node)
        cache[oid_str] = node

    def _safe_location(self, label: tuple[str, ...]):
        try:
            return self._parser.view.get_node_location(label)
        except error.SmiError:
            return None, None, ()

    def _probe(self, module, sym, oid):
        """探测节点类型与属性。返回 (type, syntax, access, status, desc, units, index_specs)。"""
        node_type = NodeType.SUBTREE
        syntax = access = status = desc = units = None
        index_specs: list[IndexSpec] | None = None

        if module and sym:
            try:
                (raw,) = self._parser._builder.import_symbols(module, sym)
                syntax, access, status, desc, units = self._read_attrs(raw)
                node_type, index_specs = self._classify(raw, module, oid)
            except error.SmiError:
                pass
        return node_type, syntax, access, status, desc, units, index_specs

    def _read_attrs(self, raw):
        syntax = getattr(getattr(raw, "getSyntax", lambda: None), "prettyPrint", lambda: None)()
        access = self._call(raw, "getMaxAccess")
        status = self._call(raw, "getStatus")
        desc = self._call(raw, "getDescription")
        units = self._call(raw, "getUnits")
        return syntax, access, status, desc, units

    def _call(self, raw, method):
        fn = getattr(raw, method, None)
        try:
            return fn() if callable(fn) else None
        except Exception:
            return None

    def _classify(self, raw, module, oid):
        """根据 PySnmp 节点对象类型推断 NodeType,并提取索引定义。"""
        node_type = NodeType.SUBTREE
        index_specs: list[IndexSpec] | None = None
        cls_name = type(raw).__name__

        if "MibTable" in cls_name:
            node_type = NodeType.TABLE
        elif "MibTableRow" in cls_name:
            node_type = NodeType.ROW
            index_specs = self._extract_index_specs(raw)
        elif "MibTableColumn" in cls_name:
            node_type = NodeType.COLUMN
        elif "MibScalar" in cls_name:
            node_type = NodeType.SCALAR
        return node_type, index_specs

    def _extract_index_specs(self, row_node) -> list[IndexSpec]:
        """从 ROW 节点提取 INDEX 列定义。"""
        specs: list[IndexSpec] = []
        try:
            indices = row_node.getIndices()  # [(name, implied, syntax), ...]
        except Exception:
            indices = []
        for idx in indices:
            if isinstance(idx, tuple) and len(idx) >= 1:
                name = idx[0]
                implied = idx[1] if len(idx) > 1 else False
                syntax = idx[2] if len(idx) > 2 else "INTEGER"
            else:
                name = str(idx); implied = False; syntax = "INTEGER"
            col_oid = self._safe_col_oid(name)
            specs.append(IndexSpec(column_name=name, column_oid=col_oid,
                                   implied=bool(implied), syntax=str(syntax)))
        return specs

    def _safe_col_oid(self, name: str) -> str:
        try:
            oid_tuple, _, _ = self._parser.view.get_node_name((name,))
            return ".".join(map(str, oid_tuple))
        except error.SmiError:
            return ""
```

> **实现说明:** PySnmp 内部节点对象类名与 getter 方法在不同小版本略有差异。`_classify` 用类名包含匹配以稳健处理。`getIndices()` 返回结构若与假设不符,测试会暴露,届时据实微调字段索引。这是 PySnmp 内省的固有不确定性,测试 fixture(IF-MIB)会锁定行为。

- [ ] **Step 4: 运行测试验证通过(可能需微调内省)**

Run: `uv run pytest tests/kernel/test_tree_builder.py -v`
Expected: 6 passed。若 `_extract_index_specs` 或 `_read_attrs` 报错,先运行下述探测脚本查看 PySnmp 实际 API:

```bash
uv run python -c "
from pysnmp.smi import builder, view, compiler
b = builder.MibBuilder()
compiler.add_mib_compiler(b, sources=['file://$(pwd)/tests/fixtures/mibs'])
b.load_modules('IF-MIB')
(row,) = b.import_symbols('IF-MIB', 'ifEntry')
print('type:', type(row).__name__)
print('indices:', row.getIndices())
print('methods:', [m for m in dir(row) if not m.startswith('_')][:40])
"
```

根据真实输出调整 `_extract_index_specs` / `_read_attrs` 中的字段访问,再跑测试。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(kernel): add MibTreeBuilder with node-type inference"
```

### Task 3.2: MibNode.find 方法(按 OID 查找)

**Files:**
- Modify: `src/hwtransmib/kernel/model.py`

> `find` 在 Task 3.1 测试中已被使用,本任务补全其实现。

- [ ] **Step 1: 在 model.py 的 MibNode 中添加 find 方法**

在 `name_path` property 之后添加:

```python
    def find(self, oid: str) -> "MibNode | None":
        """在本子树中按完整 OID 查找节点。"""
        if self.oid == oid:
            return self
        if not oid.startswith(self.oid + "."):
            return None
        for child in self.children:
            found = child.find(oid)
            if found is not None:
                return found
        return None
```

- [ ] **Step 2: 运行树构建测试验证**

Run: `uv run pytest tests/kernel/test_tree_builder.py -v`
Expected: 6 passed(`find_*` 用例通过)。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat(kernel): add MibNode.find by OID"
```

---

## 阶段 4:内核层 — OID 构造引擎(核心)

> 这是整个应用的核心难点。复用 PySnmp `getInstIdFromIndices` 的原生编码能力,而非自己实现 SNMP 索引编码规则。

### Task 4.1: OidBuilder — 标量与表列构造

**Files:**
- Create: `src/hwtransmib/kernel/oid_builder.py`
- Test: `tests/kernel/test_oid_builder.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/kernel/test_oid_builder.py
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import IndexSpec, MibNode, NodeType
from hwtransmib.kernel.oid_builder import OidBuildError, OidBuilder
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def builder(fixtures_mibs_dir):
    parser = MibParser(extra_sources=[str(fixtures_mibs_dir)])
    parser.parse(["IF-MIB"])
    root = MibTreeBuilder(parser).build()
    return OidBuilder(parser=parser, root=root)


def _find(root, oid):
    node = root.find(oid)
    assert node is not None, f"未找到节点 {oid}"
    return node


def test_scalar_appends_zero(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.1")  # ifNumber 标量
    node.node_type = NodeType.SCALAR  # 确保类型
    result = builder.build(node, {})
    assert result == "1.3.6.1.2.1.2.1.0"


def test_column_single_integer_index(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")  # ifDescr
    result = builder.build(node, {"ifIndex": "5"})
    assert result == "1.3.6.1.2.1.2.2.1.2.5"


def test_column_requires_index(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")  # ifDescr(COLUMN)
    with pytest.raises(OidBuildError):
        builder.build(node, {})


def test_column_non_integer_rejected(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    with pytest.raises(OidBuildError):
        builder.build(node, {"ifIndex": "abc"})


def test_non_constructible_node_raises(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2")  # ifTable
    with pytest.raises(OidBuildError):
        builder.build(node, {})


def test_validate_returns_errors(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    errors = builder.validate(node, {"ifIndex": "abc"})
    assert any("ifIndex" in e for e in errors)


def test_validate_ok(builder):
    node = _find(builder._root, "1.3.6.1.2.1.2.2.1.2")
    errors = builder.validate(node, {"ifIndex": "5"})
    assert errors == []
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/kernel/test_oid_builder.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 oid_builder.py**

```python
# src/hwtransmib/kernel/oid_builder.py
"""OID 构造引擎。复用 PySnmp getInstIdFromIndices 的 SNMP 索引编码能力。"""
from __future__ import annotations

from pysnmp.smi import error as smi_error

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import MibNode, NodeType


class OidBuildError(Exception):
    """OID 构造错误。"""


class OidBuilder:
    """构造完整 OID 访问字符串。

    标量:基础 OID + ".0"
    表列:基础 OID + 索引实例后缀(由 PySnmp getInstIdFromIndices 编码)
    """

    def __init__(self, parser: MibParser, root: MibNode) -> None:
        self._parser = parser
        self._root = root

    def build(self, node: MibNode, index_values: dict[str, str]) -> str:
        """构造并返回完整 OID。校验失败抛 OidBuildError。"""
        errors = self.validate(node, index_values)
        if errors:
            raise OidBuildError("; ".join(errors))

        if node.node_type == NodeType.SCALAR:
            return f"{node.oid}.0"
        if node.node_type == NodeType.COLUMN:
            return self._build_column(node, index_values)
        raise OidBuildError(f"节点 {node.name} 不可构造(类型 {node.node_type.value})")

    def validate(self, node: MibNode, index_values: dict[str, str]) -> list[str]:
        """返回校验错误列表(空列表表示通过)。"""
        errors: list[str] = []
        if not node.is_constructible:
            errors.append(f"节点 {node.name} 不可构造")
            return errors

        specs = self._row_index_specs(node)
        for spec in specs:
            raw = index_values.get(spec.column_name, "").strip()
            if raw == "":
                errors.append(f"索引 {spec.column_name} 未填写")
                continue
            errors.extend(self._validate_value(spec, raw))
        return errors

    def _build_column(self, node: MibNode, index_values: dict[str, str]) -> str:
        specs = self._row_index_specs(node)
        row_node = self._row_raw_node(node)
        if row_node is None:
            raise OidBuildError(f"找不到节点 {node.name} 所属的表行定义")

        # 按索引列声明顺序构造类型化值
        typed_values = []
        for spec in specs:
            raw = index_values[spec.column_name].strip()
            typed_values.append(self._coerce(spec, raw))

        try:
            inst_id = row_node.getInstIdFromIndices(*typed_values)
        except (smi_error.SmiError, ValueError, TypeError) as exc:
            raise OidBuildError(f"索引编码失败: {exc}") from exc

        suffix = ".".join(map(str, tuple(inst_id)))
        # getInstIdFromIndices 返回完整实例 OID(含 column base 后缀)
        # 若返回值已含完整路径则直接用,否则拼接
        full = suffix if suffix.startswith(node.oid) else f"{node.oid}.{suffix}"
        return full

    def _row_index_specs(self, node: MibNode):
        parent = node.parent
        while parent is not None:
            if parent.index_specs:
                return parent.index_specs
            parent = parent.parent
        return []

    def _row_raw_node(self, node: MibNode):
        """返回所属 ROW 的 PySnmp 原生节点对象。"""
        ancestor = node.parent
        while ancestor is not None:
            if ancestor.node_type == NodeType.ROW and ancestor.module_name:
                try:
                    (raw,) = self._parser._builder.import_symbols(
                        ancestor.module_name, ancestor.name
                    )
                    return raw
                except smi_error.SmiError:
                    return None
            ancestor = ancestor.parent
        return None

    def _coerce(self, spec, raw: str):
        """将字符串输入转为 PySnmp 期望的索引值类型。"""
        syntax = spec.syntax.upper()
        if "INT" in syntax:
            try:
                return int(raw)
            except ValueError:
                raise OidBuildError(f"{spec.column_name} 需要整数,得到 {raw!r}")
        # 字符串/IP/MAC 直接传字符串,PySnmp 按 INDEX syntax 编码
        return raw

    def _validate_value(self, spec, raw: str) -> list[str]:
        syntax = spec.syntax.upper()
        if "INT" in syntax:
            try:
                int(raw)
            except ValueError:
                return [f"{spec.column_name} 需要整数,得到 {raw!r}"]
        return []
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/kernel/test_oid_builder.py -v`
Expected: 7 passed。若 `getInstIdFromIndices` 返回结构不符(如已含/不含 column 前缀),用调试脚本确认:

```bash
uv run python -c "
from pysnmp.smi import builder, view, compiler
b = builder.MibBuilder()
compiler.add_mib_compiler(b, sources=['file://$(pwd)/tests/fixtures/mibs'])
b.load_modules('IF-MIB')
(row,) = b.import_symbols('IF-MIB', 'ifEntry')
inst = row.getInstIdFromIndices(5)
print('inst tuple:', tuple(inst))
print('inst str:', str(inst))
"
```

根据真实输出调整 `_build_column` 的拼接逻辑(决定用 `suffix` 还是 `full`)。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(kernel): add OidBuilder reusing PySnmp index encoding"
```

---

## 阶段 5:内核层 — 搜索索引

### Task 5.1: SearchIndex 名称 + OID 搜索

**Files:**
- Create: `src/hwtransmib/kernel/search_index.py`
- Test: `tests/kernel/test_search_index.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/kernel/test_search_index.py
from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.kernel.search_index import SearchIndex


def _make_tree() -> MibNode:
    root = MibNode("1.3", "org", NodeType.SUBTREE)
    a = MibNode("1.3.6.1.2.1.2.2.1.2", "ifDescr", NodeType.COLUMN,
                description="A textual string about the interface", parent=root)
    b = MibNode("1.3.6.1.2.1.1.1", "sysDescr", NodeType.SCALAR, parent=root)
    root.children = [a, b]
    return root


def test_search_by_name_substring():
    idx = SearchIndex(_make_tree())
    results = idx.search("descr")
    names = [r.name for r in results]
    assert "ifDescr" in names
    assert "sysDescr" in names


def test_search_by_oid_substring():
    idx = SearchIndex(_make_tree())
    results = idx.search("2.2.1.2")
    assert any(r.name == "ifDescr" for r in results)


def test_search_case_insensitive():
    idx = SearchIndex(_make_tree())
    results = idx.search("IFDESCR")
    assert any(r.name == "ifDescr" for r in results)


def test_search_by_description_keyword():
    idx = SearchIndex(_make_tree())
    results = idx.search("interface")
    assert any(r.name == "ifDescr" for r in results)


def test_search_no_match():
    idx = SearchIndex(_make_tree())
    assert idx.search("zzzznotfound") == []


def test_search_exact_oid_jump():
    idx = SearchIndex(_make_tree())
    results = idx.search("1.3.6.1.2.1.2.2.1.2")
    assert results and results[0].name == "ifDescr"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/kernel/test_search_index.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 search_index.py**

```python
# src/hwtransmib/kernel/search_index.py
"""MIB 节点搜索索引:按名称/OID/描述模糊匹配。"""
from __future__ import annotations

from hwtransmib.kernel.model import MibNode


class SearchIndex:
    """对所有节点建立索引,支持名称/OID/描述的子串匹配(不区分大小写)。"""

    def __init__(self, root: MibNode) -> None:
        self._nodes: list[MibNode] = []
        self._collect(root)

    def _collect(self, node: MibNode) -> None:
        self._nodes.append(node)
        for child in node.children:
            self._collect(child)

    def search(self, query: str, limit: int = 100) -> list[MibNode]:
        """返回匹配节点。完整 OID 精确匹配优先排在首位。"""
        q = query.strip().lower()
        if not q:
            return []
        exact: list[MibNode] = []
        partial: list[MibNode] = []
        for node in self._nodes:
            oid = node.oid.lower()
            name = node.name.lower()
            desc = (node.description or "").lower()
            if node.oid == query.strip():
                exact.append(node)
            elif q in name or q in oid or q in desc:
                partial.append(node)
            if len(exact) + len(partial) >= limit:
                break
        # 去重(精确匹配可能也命中子串)
        seen = {n.oid for n in exact}
        return exact + [n for n in partial if n.oid not in seen]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/kernel/test_search_index.py -v`
Expected: 6 passed。

- [ ] **Step 5: 运行全部内核测试确认无回归**

Run: `uv run pytest tests/kernel/ -v`
Expected: 全部 passed。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(kernel): add SearchIndex for name/oid/description matching"
```

---

## 阶段 6:持久化层

### Task 6.1: JsonStore 原子读写

**Files:**
- Create: `src/hwtransmib/persistence/json_store.py`
- Test: `tests/persistence/test_json_store.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/persistence/test_json_store.py
import json
from pathlib import Path

from hwtransmib.persistence.json_store import JsonStore


def test_write_then_read(tmp_path: Path):
    store = JsonStore(tmp_path / "data.json", default={"items": []})
    store.write({"items": [1, 2, 3]})
    assert store.read() == {"items": [1, 2, 3]}


def test_default_when_missing(tmp_path: Path):
    store = JsonStore(tmp_path / "missing.json", default={"a": 1})
    assert store.read() == {"a": 1}


def test_corrupt_file_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{ not valid json")
    store = JsonStore(path, default={"x": 0})
    assert store.read() == {"x": 0}


def test_corrupt_file_is_backed_up(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{ broken")
    JsonStore(path, default={})
    backups = list(tmp_path.glob("bad.json.corrupt.*"))
    assert len(backups) == 1


def test_atomic_write_no_partial_file(tmp_path: Path):
    path = tmp_path / "data.json"
    store = JsonStore(path, default={})
    store.write({"k": "v"})
    # 文件应存在且内容完整
    assert json.loads(path.read_text()) == {"k": "v"}
    # 不应残留临时文件
    assert list(tmp_path.glob("*.tmp")) == []
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/persistence/test_json_store.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 json_store.py**

```python
# src/hwtransmib/persistence/json_store.py
"""JSON 文件存储,原子写入 + 损坏时备份回退。"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonStore:
    """单个 JSON 文件的读写封装。

    写入采用临时文件 + rename(原子操作),避免崩溃损坏。
    读取时若 JSON 损坏,备份原文件后回退到默认值。
    """

    def __init__(self, path: Path, default: dict[str, Any]) -> None:
        self._path = Path(path)
        self._default = default
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self._path.exists():
            return dict(self._default)
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._backup_corrupt()
            return dict(self._default)

    def write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写:同目录临时文件 + os.replace
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp", prefix=self._path.name + "."
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _backup_corrupt(self) -> None:
        import time
        backup = self._path.with_suffix(
            self._path.suffix + f".corrupt.{int(time.time())}"
        )
        try:
            os.replace(self._path, backup)
        except OSError:
            pass
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/persistence/test_json_store.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(persistence): add JsonStore with atomic write and corrupt fallback"
```

### Task 6.2: 用户数据目录 + 四个存储文件封装

**Files:**
- Create: `src/hwtransmib/persistence/user_data.py`
- Test: `tests/persistence/test_user_data.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/persistence/test_user_data.py
from hwtransmib.persistence.user_data import UserData


def test_defaults(tmp_path):
    ud = UserData(base_dir=tmp_path)
    assert ud.config() == {"window_geometry": None, "detail_visible": True,
                           "split_sizes": None}
    assert ud.imports() == {"files": []}
    assert ud.favorites() == {"items": []}
    assert ud.history() == {"items": []}


def test_persist_imports(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.set_imports(["/a/IF-MIB", "/b/IP-MIB"])
    ud2 = UserData(base_dir=tmp_path)
    assert ud2.imports() == {"files": ["/a/IF-MIB", "/b/IP-MIB"]}


def test_history_lru_eviction(tmp_path):
    ud = UserData(base_dir=tmp_path, history_limit=3)
    ud.add_history_entry({"oid": "1.1"})
    ud.add_history_entry({"oid": "1.2"})
    ud.add_history_entry({"oid": "1.3"})
    ud.add_history_entry({"oid": "1.4"})  # 应淘汰 1.1
    items = ud.history()["items"]
    assert [e["oid"] for e in items] == ["1.4", "1.3", "1.2"]


def test_add_favorite(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.add_favorite({"oid": "1.3.6.1.2.1.1.1", "name": "sysDescr"})
    assert len(ud.favorites()["items"]) == 1


def test_remove_favorite(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.add_favorite({"oid": "1.1", "name": "a"})
    ud.remove_favorite("1.1")
    assert ud.favorites()["items"] == []
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/persistence/test_user_data.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 user_data.py**

```python
# src/hwtransmib/persistence/user_data.py
"""用户数据管理:config/imports/favorites/history 四个 JSON 存储。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from hwtransmib.persistence.json_store import JsonStore

_DEFAULT_HISTORY_LIMIT = 200


class UserData:
    """管理 ~/.hwtransmib/ 下的用户数据文件。"""

    def __init__(self, base_dir: Path | None = None,
                 history_limit: int = _DEFAULT_HISTORY_LIMIT) -> None:
        self._base = Path(base_dir) if base_dir else Path.home() / ".hwtransmib"
        self._limit = history_limit
        self._config = JsonStore(self._base / "config.json", {
            "window_geometry": None,
            "detail_visible": True,
            "split_sizes": None,
        })
        self._imports = JsonStore(self._base / "imports.json", {"files": []})
        self._favorites = JsonStore(self._base / "favorites.json", {"items": []})
        self._history = JsonStore(self._base / "history.json", {"items": []})

    # --- config ---
    def config(self) -> dict[str, Any]:
        return self._config.read()

    def set_config(self, data: dict[str, Any]) -> None:
        self._config.write(data)

    # --- imports ---
    def imports(self) -> dict[str, Any]:
        return self._imports.read()

    def set_imports(self, files: list[str]) -> None:
        self._imports.write({"files": files})

    # --- favorites ---
    def favorites(self) -> dict[str, Any]:
        return self._favorites.read()

    def add_favorite(self, item: dict[str, Any]) -> None:
        data = self._favorites.read()
        items = [i for i in data["items"] if i.get("oid") != item.get("oid")]
        items.insert(0, item)
        self._favorites.write({"items": items})

    def remove_favorite(self, oid: str) -> None:
        data = self._favorites.read()
        items = [i for i in data["items"] if i.get("oid") != oid]
        self._favorites.write({"items": items})

    # --- history (LRU) ---
    def history(self) -> dict[str, Any]:
        return self._history.read()

    def add_history_entry(self, entry: dict[str, Any]) -> None:
        data = self._history.read()
        items = [e for e in data["items"] if e.get("oid") != entry.get("oid")]
        items.insert(0, entry)
        items = items[: self._limit]
        self._history.write({"items": items})
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/persistence/ -v`
Expected: 全部 passed(含 user_data 5 个 + json_store 5 个)。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(persistence): add UserData with config/imports/favorites/history"
```

---

## 阶段 7:应用服务层

### Task 7.1: ImportService 导入编排

**Files:**
- Create: `src/hwtransmib/services/import_service.py`
- Test: `tests/services/test_import_service.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/services/test_import_service.py
import pytest

from hwtransmib.services.import_service import ImportReport, ImportService


@pytest.fixture
def service(fixtures_mibs_dir):
    return ImportService(extra_sources=[str(fixtures_mibs_dir)])


def test_import_returns_report(service):
    report = service.import_files([str(fixtures_mibs_dir if False else
                                       pytest.importorskip("pathlib").Path(
                                       __file__).parent.parent / "fixtures" / "mibs" / "IF-MIB")])
    assert isinstance(report, ImportReport)
    assert "IF-MIB" in report.loaded_modules
    assert report.node_count > 0


def test_get_root_after_import(service, fixtures_mibs_dir):
    service.import_files([str(fixtures_mibs_dir / "IF-MIB")])
    root = service.get_root()
    assert root.oid == "1.3"


def test_import_reports_missing_file(service):
    report = service.import_files(["/nonexistent/Fake-MIB"])
    assert report.errors  # 有错误
```

> 注:第一个测试的路径表达式较绕,下个 step 用更干净的 fixture 路径。先让它失败,再修正实现。

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/services/test_import_service.py -v`
Expected: FAIL(ImportError + 可能路径问题)。

- [ ] **Step 3: 修正测试中路径,改用 if_mib_path fixture 干净写法**

将 `test_import_returns_report` 改为:

```python
def test_import_returns_report(service, if_mib_path):
    report = service.import_files([str(if_mib_path)])
    assert isinstance(report, ImportReport)
    assert "IF-MIB" in report.loaded_modules
    assert report.node_count > 0
```

- [ ] **Step 4: 实现 import_service.py**

```python
# src/hwtransmib/services/import_service.py
"""导入编排服务:从文件路径解析 MIB,构建树,返回报告。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import MibNode
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@dataclass
class ImportReport:
    loaded_modules: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    node_count: int = 0


class ImportService:
    """MIB 文件导入服务。"""

    def __init__(self, extra_sources: list[str] | None = None) -> None:
        self._sources = list(extra_sources or [])
        self._parser: MibParser | None = None
        self._root: MibNode | None = None

    def import_files(self, file_paths: list[str]) -> ImportReport:
        report = ImportReport()
        # 文件目录加入 source,从中提取模块名
        source_dirs = set(self._sources)
        module_names: list[str] = []
        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                report.errors.append(f"文件不存在: {fp}")
                continue
            source_dirs.add(str(path.parent))
            module_names.append(self._module_name_of(path))
        source_dirs.discard("")

        self._parser = MibParser(extra_sources=list(source_dirs))
        result = self._parser.parse(module_names)
        report.loaded_modules = result.loaded_modules
        report.errors.extend(result.errors)
        if result.loaded_modules:
            self._root = MibTreeBuilder(self._parser).build()
            report.node_count = self._count(self._root)
        return report

    def get_root(self) -> MibNode:
        if self._root is None:
            raise RuntimeError("尚未导入任何 MIB")
        return self._root

    def get_parser(self) -> MibParser:
        if self._parser is None:
            raise RuntimeError("尚未导入任何 MIB")
        return self._parser

    def _module_name_of(self, path: Path) -> str:
        # MIB 文件名通常即模块名;去掉扩展名和数字版本后缀
        name = path.name
        name = re.split(r"[.](txt|mib|my)$", name)[0]
        return name

    def _count(self, node: MibNode) -> int:
        n = 1
        for c in node.children:
            n += self._count(c)
        return n
```

- [ ] **Step 5: 运行测试验证通过**

Run: `uv run pytest tests/services/test_import_service.py -v`
Expected: 3 passed。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(services): add ImportService orchestration"
```

### Task 7.2: OidBuildService 构造 + 历史

**Files:**
- Create: `src/hwtransmib/services/oid_build_service.py`
- Test: `tests/services/test_oid_build_service.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/services/test_oid_build_service.py
import pytest

from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.services.oid_build_service import OidBuildService


@pytest.fixture
def setup(fixtures_mibs_dir, tmp_path):
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
    imp.import_files([str(fixtures_mibs_dir / "IF-MIB")])
    root = imp.get_root()
    parser = imp.get_parser()
    ud = UserData(base_dir=tmp_path)
    return OidBuildService(parser=parser, root=root, user_data=ud), root, ud


def test_build_records_history(setup):
    svc, root, ud = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")  # ifDescr
    oid = svc.build_and_record(node, {"ifIndex": "5"})
    assert oid == "1.3.6.1.2.1.2.2.1.2.5"
    items = ud.history()["items"]
    assert items[0]["oid"] == oid


def test_validate_returns_errors(setup):
    svc, root, _ = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")
    errors = svc.validate(node, {"ifIndex": "abc"})
    assert errors
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/services/test_oid_build_service.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 oid_build_service.py**

```python
# src/hwtransmib/services/oid_build_service.py
"""OID 构造服务:构造 + 记录历史。"""
from __future__ import annotations

import time

from hwtransmib.kernel.model import MibNode
from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.oid_builder import OidBuildError, OidBuilder
from hwtransmib.persistence.user_data import UserData


class OidBuildService:
    """组合 OidBuilder 与历史记录。"""

    def __init__(self, parser: MibParser, root: MibNode, user_data: UserData) -> None:
        self._builder = OidBuilder(parser=parser, root=root)
        self._ud = user_data

    def validate(self, node: MibNode, index_values: dict[str, str]) -> list[str]:
        return self._builder.validate(node, index_values)

    def build_and_record(self, node: MibNode,
                         index_values: dict[str, str]) -> str:
        oid = self._builder.build(node, index_values)
        self._ud.add_history_entry({
            "oid": oid,
            "name": node.name,
            "module": node.module_name,
            "timestamp": int(time.time()),
        })
        return oid
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/services/test_oid_build_service.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(services): add OidBuildService with history recording"
```

### Task 7.3: SearchService 防抖搜索

**Files:**
- Create: `src/hwtransmib/services/search_service.py`
- Test: `tests/services/test_search_service.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/services/test_search_service.py
import pytest

from hwtransmib.services.import_service import ImportService
from hwtransmib.services.search_service import SearchService


@pytest.fixture
def service(fixtures_mibs_dir):
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
    imp.import_files([str(fixtures_mibs_dir / "IF-MIB")])
    return SearchService(root=imp.get_root())


def test_search_returns_nodes(service):
    results = service.search("ifDescr")
    assert any(r.name == "ifDescr" for r in results)


def test_search_empty_query_returns_empty(service):
    assert service.search("   ") == []


def test_search_oid(service):
    results = service.search("2.2.1.2")
    assert any(r.name == "ifDescr" for r in results)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/services/test_search_service.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 search_service.py**

```python
# src/hwtransmib/services/search_service.py
"""搜索服务:封装 SearchIndex。防抖由 UI 层用 QTimer 实现。"""
from __future__ import annotations

from hwtransmib.kernel.model import MibNode
from hwtransmib.kernel.search_index import SearchIndex


class SearchService:
    """MIB 节点搜索。UI 层负责 200ms 防抖。"""

    def __init__(self, root: MibNode) -> None:
        self._index = SearchIndex(root)

    def rebuild(self, root: MibNode) -> None:
        self._index = SearchIndex(root)

    def search(self, query: str, limit: int = 100) -> list[MibNode]:
        return self._index.search(query, limit=limit)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/services/ -v`
Expected: 全部 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(services): add SearchService"
```

---

## 阶段 8:UI 层(PySide6)

> UI 层用 pytest-qt 测试关键交互。为避免 UI 卡在解析,导入在 QThread 中执行。

### Task 8.1: MibTreeModel(QAbstractItemModel)

**Files:**
- Create: `src/hwtransmib/ui/mib_tree_model.py`
- Test: `tests/ui/test_mib_tree_model.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/ui/test_mib_tree_model.py
import pytest

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.ui.mib_tree_model import MibTreeModel


def _tree() -> MibNode:
    root = MibNode("1.3", "org", NodeType.SUBTREE)
    c = MibNode("1.3.6", "dod", NodeType.SUBTREE, parent=root)
    leaf = MibNode("1.3.6.1.2.1.1.1", "sysDescr", NodeType.SCALAR, parent=c)
    root.children = [c]
    c.children = [leaf]
    return root


def test_root_index(qtmodeltester):
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    assert root_idx.data() == "org"


def test_row_count(qtmodeltester):
    model = MibTreeModel(_tree())
    qtmodeltester.check(model)


def test_column_count():
    model = MibTreeModel(_tree())
    assert model.columnCount() == 2  # 名称 + OID


def test_oid_column_data():
    model = MibTreeModel(_tree())
    root_idx = model.index(0, 0)
    oid_idx = model.index(0, 1, root_idx)
    assert oid_idx.data().startswith("1.3.6")


def test_node_from_index():
    model = MibTreeModel(_tree())
    idx = model.index(0, 0)
    node = model.node_from_index(idx)
    assert node.name == "org"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/ui/test_mib_tree_model.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 mib_tree_model.py**

```python
# src/hwtransmib/ui/mib_tree_model.py
"""MIB 树的 QAbstractItemModel 实现。"""
from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from hwtransmib.kernel.model import MibNode, NodeType

_ICON = {
    NodeType.MODULE: "📦", NodeType.SUBTREE: "📁", NodeType.SCALAR: "🟢",
    NodeType.TABLE: "🔴", NodeType.ROW: "🔴", NodeType.COLUMN: "🟢",
}


class MibTreeModel(QAbstractItemModel):
    """两列:名称(带图标)、OID。"""

    def __init__(self, root: MibNode) -> None:
        super().__init__()
        # 用一个虚拟根,使顶层只有一个节点
        self._invisible = MibNode("", "", NodeType.SUBTREE)
        self._invisible.children = [root]
        root.parent = self._invisible

    def index(self, row, column, parent=QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = self._node_from_index(parent)
        child = parent_node.children[row]
        return self.createIndex(row, column, child)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        node = self._node_from_index(index)
        parent = node.parent
        if parent is None or parent is self._invisible:
            return QModelIndex()
        grand = parent.parent or self._invisible
        row = grand.children.index(parent)
        return self.createIndex(row, 0, parent)

    def rowCount(self, parent=QModelIndex()):
        return len(self._node_from_index(parent).children)

    def columnCount(self, parent=QModelIndex()):
        return 2

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node = self._node_from_index(index)
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                icon = _ICON.get(node.node_type, "")
                return f"{icon} {node.name}"
            return node.oid
        if role == Qt.ItemDataRole.UserRole:
            return node
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return ["节点", "OID"][section]
        return None

    def _node_from_index(self, index) -> MibNode:
        if index.isValid():
            return index.internalPointer()
        return self._invisible

    def node_from_index(self, index) -> MibNode:
        return self._node_from_index(index)

    def reset_root(self, root: MibNode) -> None:
        self.beginResetModel()
        self._invisible.children = [root]
        root.parent = self._invisible
        self.endResetModel()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/ui/test_mib_tree_model.py -v`
Expected: 5 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(ui): add MibTreeModel QAbstractItemModel"
```

### Task 8.2: PropertyPanel 属性面板

**Files:**
- Create: `src/hwtransmib/ui/property_panel.py`

- [ ] **Step 1: 实现 property_panel.py**

```python
# src/hwtransmib/ui/property_panel.py
"""节点属性面板:键值对表格展示。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from hwtransmib.kernel.model import MibNode


class PropertyPanel(QWidget):
    """以两列表格(属性 / 值)展示节点元数据。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self._title = QLabel("属性")
        layout.addWidget(self._title)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["属性", "值"])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

    def show_node(self, node: MibNode) -> None:
        rows = [
            ("名称", node.name),
            ("完整 OID", node.oid),
            ("类型", node.node_type.value),
            ("SYNTAX", node.syntax or "—"),
            ("MAX-ACCESS", node.access or "—"),
            ("STATUS", node.status or "—"),
            ("UNITS", node.units or "—"),
            ("所属模块", node.module_name or "—"),
            ("DESCRIPTION", node.description or "—"),
        ]
        self._title.setText(f"属性 — {node.name}")
        self._table.setRowCount(len(rows))
        for r, (k, v) in enumerate(rows):
            self._table.setItem(r, 0, QTableWidgetItem(k))
            self._table.setItem(r, 1, QTableWidgetItem(str(v)))
```

- [ ] **Step 2: 冒烟测试可实例化**

```bash
uv run python -c "
from PySide6.QtWidgets import QApplication
from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.ui.property_panel import PropertyPanel
app = QApplication([])
n = MibNode('1.2.3', 'test', NodeType.SCALAR, syntax='INT', access='ro')
p = PropertyPanel(); p.show_node(n)
print('PropertyPanel ok')
"
```
Expected: 输出 `PropertyPanel ok`。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat(ui): add PropertyPanel key-value table"
```

### Task 8.3: OidBuilderDialog 构造表单 + 实时预览

**Files:**
- Create: `src/hwtransmib/ui/oid_builder_dialog.py`
- Test: `tests/ui/test_oid_builder_dialog.py`

- [ ] **Step 1: 编写失败测试**

```python
# tests/ui/test_oid_builder_dialog.py
import pytest

from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.ui.oid_builder_dialog import OidBuilderDialog


@pytest.fixture
def setup(fixtures_mibs_dir, tmp_path):
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
    imp.import_files([str(fixtures_mibs_dir / "IF-MIB")])
    from hwtransmib.services.oid_build_service import OidBuildService
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    return svc, imp.get_root()


def test_scalar_dialog_shows_zero(qtbot, setup):
    svc, root = setup
    node = root.find("1.3.6.1.2.1.2.1")  # ifNumber 标量
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    assert ".0" in dlg.result_text()


def test_column_dialog_updates_on_input(qtbot, setup):
    svc, root = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")  # ifDescr
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    dlg.set_index_value("ifIndex", "7")
    assert dlg.result_text().endswith(".7")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/ui/test_oid_builder_dialog.py -v`
Expected: FAIL(ImportError)。

- [ ] **Step 3: 实现 oid_builder_dialog.py**

```python
# src/hwtransmib/ui/oid_builder_dialog.py
"""OID 构造对话框:根据节点类型展示表单,实时预览结果。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.kernel.oid_builder import OidBuildError
from hwtransmib.services.oid_build_service import OidBuildService


class OidBuilderDialog(QDialog):
    """标量:显示 .0 结果;表列:展示索引输入框,实时预览。"""

    def __init__(self, node: MibNode, service: OidBuildService,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._node = node
        self._service = service
        self._inputs: dict[str, QLineEdit] = {}
        self.setWindowTitle(f"构造 OID — {node.name}")
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        info = QLabel(f"节点:<b>{self._node.name}</b>  基础 OID:{self._node.oid}")
        layout.addWidget(info)

        specs = self._row_specs()
        if specs:
            form = QFormLayout()
            for spec in specs:
                edit = QLineEdit()
                edit.setPlaceholderText(spec.syntax)
                edit.textChanged.connect(self._refresh)
                self._inputs[spec.column_name] = edit
                form.addRow(f"{spec.column_name} ({spec.syntax})", edit)
            layout.addLayout(form)
        elif self._node.node_type == NodeType.SCALAR:
            layout.addWidget(QLabel("标量节点,自动追加 .0 实例后缀"))

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setMaximumHeight(60)
        layout.addWidget(self._preview)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("📋 复制 OID")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)
        cancel_btn = QPushButton("关闭")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _row_specs(self):
        parent = self._node.parent
        while parent is not None:
            if parent.index_specs:
                return parent.index_specs
            parent = parent.parent
        return []

    def set_index_value(self, column_name: str, value: str) -> None:
        edit = self._inputs.get(column_name)
        if edit is not None:
            edit.setText(value)

    def result_text(self) -> str:
        return self._preview.toPlainText()

    def _values(self) -> dict[str, str]:
        return {name: e.text() for name, e in self._inputs.items()}

    def _refresh(self) -> None:
        values = self._values()
        errors = self._service.validate(self._node, values)
        if errors:
            self._preview.setPlainText("⚠ " + "; ".join(errors))
            return
        try:
            oid = self._service._builder.build(self._node, values)
            self._preview.setPlainText(oid)
        except OidBuildError as exc:
            self._preview.setPlainText("⚠ " + str(exc))

    def _copy(self) -> None:
        errors = self._service.validate(self._node, self._values())
        if errors:
            QMessageBox.warning(self, "无法复制", "; ".join(errors))
            return
        oid = self._service.build_and_record(self._node, self._values())
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(oid)
        QMessageBox.information(self, "已复制", oid)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/ui/test_oid_builder_dialog.py -v`
Expected: 2 passed。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(ui): add OidBuilderDialog with live preview"
```

### Task 8.4: SearchBox 防抖搜索框

**Files:**
- Create: `src/hwtransmib/ui/search_box.py`

- [ ] **Step 1: 实现 search_box.py**

```python
# src/hwtransmib/ui/search_box.py
"""搜索框:200ms 防抖,触发搜索信号。"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QLineEdit


class SearchBox(QLineEdit):
    """输入停止 200ms 后发出 search_requested 信号。"""

    search_requested = Signal(str)

    def __init__(self, parent=None, debounce_ms: int = 200) -> None:
        super().__init__(parent)
        self.setPlaceholderText("🔍 搜索 节点名称 / OID...")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(debounce_ms)
        self._timer.timeout.connect(self._emit)
        self.textChanged.connect(self._schedule)

    def _schedule(self) -> None:
        self._timer.start()

    def _emit(self) -> None:
        self.search_requested.emit(self.text().strip())
```

- [ ] **Step 2: 冒烟测试**

```bash
uv run python -c "
from PySide6.QtWidgets import QApplication
from hwtransmib.ui.search_box import SearchBox
app = QApplication([])
s = SearchBox()
print('SearchBox ok')
"
```
Expected: 输出 `SearchBox ok`。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat(ui): add SearchBox with debounce"
```

### Task 8.5: MainWindow 主窗口集成

**Files:**
- Create: `src/hwtransmib/ui/main_window.py`

- [ ] **Step 1: 实现 main_window.py**

```python
# src/hwtransmib/ui/main_window.py
"""主窗口:MIB 树(上) + 可折叠详情区(下,含属性面板与三 Tab)。"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSplitter, QTabWidget, QTableView, QTreeView, QVBoxLayout,
    QWidget,
)

from hwtransmib.kernel.model import MibNode
from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportReport, ImportService
from hwtransmib.services.oid_build_service import OidBuildService
from hwtransmib.services.search_service import SearchService
from hwtransmib.ui.mib_tree_model import MibTreeModel
from hwtransmib.ui.oid_builder_dialog import OidBuilderDialog
from hwtransmib.ui.property_panel import PropertyPanel
from hwtransmib.ui.search_box import SearchBox


class MainWindow(QMainWindow):
    def __init__(self, import_service: ImportService, user_data: UserData) -> None:
        super().__init__()
        self.setWindowTitle("🌲 HWTransMIB")
        self.resize(1000, 700)
        self._import = import_service
        self._ud = user_data
        self._oid_svc: OidBuildService | None = None
        self._search_svc: SearchService | None = None

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        # 工具栏区
        toolbar = QHBoxLayout()
        self._import_btn = QPushButton("📂 导入 MIB")
        self._import_btn.clicked.connect(self._on_import)
        self._search = SearchBox()
        self._search.search_requested.connect(self._on_search)
        self._detail_btn = QPushButton("📋 详情")
        self._detail_btn.setCheckable(True)
        self._detail_btn.toggled.connect(self._toggle_detail)
        toolbar.addWidget(self._import_btn)
        toolbar.addWidget(self._search, 1)
        toolbar.addWidget(self._detail_btn)
        outer.addLayout(toolbar)

        # 上下分割:树 + 详情
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._tree = QTreeView()
        self._tree.setUniformRowHeights(True)
        self._tree.doubleClicked.connect(self._on_node_activated)
        self._splitter.addWidget(self._tree)

        self._detail = self._build_detail()
        self._splitter.addWidget(self._detail)
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 1)
        outer.addWidget(self._splitter, 1)

        # 状态栏
        self._status = QLabel("就绪")
        self.statusBar().addWidget(self._status)

        # 应用持久化的显隐状态
        self._detail_btn.setChecked(self._ud.config().get("detail_visible", True))

    def _build_detail(self) -> QWidget:
        box = QGroupBox()
        layout = QHBoxLayout(box)
        self._property = PropertyPanel()
        layout.addWidget(self._property, 2)
        self._tabs = QTabWidget()
        self._fav_view = QTableView()
        self._hist_view = QTableView()
        self._tabs.addTab(self._fav_view, "★ 收藏")
        self._tabs.addTab(self._hist_view, "🕑 历史")
        layout.addWidget(self._tabs, 1)
        return box

    def _toggle_detail(self, visible: bool) -> None:
        self._detail.setVisible(visible)

    def _on_import(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 MIB 文件", "", "MIB 文件 (*.mib *.txt *.my);;所有文件 (*)"
        )
        if not paths:
            return
        report: ImportReport = self._import.import_files(paths)
        root = self._import.get_root()
        self._model = MibTreeModel(root)
        self._tree.setModel(self._model)
        self._oid_svc = OidBuildService(
            parser=self._import.get_parser(), root=root, user_data=self._ud
        )
        self._search_svc = SearchService(root=root)
        self._ud.set_imports(paths)
        self._status.setText(
            f"已加载 {len(report.loaded_modules)} 个 MIB · {report.node_count} 节点"
        )
        if report.errors:
            QMessageBox.warning(self, "部分导入失败", "\n".join(report.errors))

    def _current_node(self) -> MibNode | None:
        idx = self._tree.currentIndex()
        model = self._tree.model()
        if model is None or not idx.isValid():
            return None
        return model.node_from_index(idx)

    def _on_node_activated(self) -> None:
        if not self._detail_btn.isChecked():
            self._detail_btn.setChecked(True)
        node = self._current_node()
        if node:
            self._property.show_node(node)

    def _on_search(self, query: str) -> None:
        if self._search_svc is None or not query:
            return
        results = self._search_svc.search(query)
        if results:
            node = results[0]
            self._select_node(node)

    def _select_node(self, node: MibNode) -> None:
        # 简化:选根;完整实现需按 OID 路径展开
        self._property.show_node(node)
        if node.is_constructible:
            self._open_builder(node)

    def _open_builder(self, node: MibNode) -> None:
        if self._oid_svc is None:
            return
        dlg = OidBuilderDialog(node, self._oid_svc, self)
        dlg.exec()

    def closeEvent(self, event) -> None:
        cfg = self._ud.config()
        cfg["detail_visible"] = self._detail_btn.isChecked()
        self._ud.set_config(cfg)
        super().closeEvent(event)
```

- [ ] **Step 2: 冒烟测试(无导入启动)**

```bash
uv run python -c "
from PySide6.QtWidgets import QApplication
from hwtransmib.ui.main_window import MainWindow
from hwtransmib.services.import_service import ImportService
from hwtransmib.persistence.user_data import UserData
import tempfile
app = QApplication([])
w = MainWindow(ImportService(), UserData(base_dir=__import__('pathlib').Path(tempfile.mkdtemp())))
print('MainWindow ok')
"
```
Expected: 输出 `MainWindow ok`。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat(ui): add MainWindow with tree + collapsible detail"
```

### Task 8.6: app.py 入口

**Files:**
- Create: `src/hwtransmib/ui/app.py`

- [ ] **Step 1: 实现 app.py**

```python
# src/hwtransmib/ui/app.py
"""应用入口。"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    # 内置标准 MIB 库随包分发
    import importlib.resources
    std_dir = importlib.resources.files("hwtransmib.kernel") / "standard_mibs"
    sources = [str(std_dir)] if std_dir.is_dir() else []

    window = MainWindow(
        import_service=ImportService(extra_sources=sources),
        user_data=UserData(),
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行应用冒烟**

```bash
uv run hwtransmib
```
Expected: 窗口弹出,无报错(可手动关闭)。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat(ui): add app entry point"
```

---

## 阶段 9:内置标准 MIB 库 + 全量验证

### Task 9.1: 打包内置标准 MIB

**Files:**
- Create: `src/hwtransmib/kernel/standard_mibs/`(目录 + 文件)

- [ ] **Step 1: 下载常用标准 MIB 到内置目录**

```bash
mkdir -p src/hwtransmib/kernel/standard_mibs
cd src/hwtransmib/kernel/standard_mibs
for m in SNMPv2-SMI SNMPv2-TC SNMPv2-MIB IF-MIB IP-MIB TCP-MIB UDP-MIB; do
  curl -fsSL -o "$m" "https://raw.githubusercontent.com/lextudio/pysnmp/master/pysnmp/smi/mibs/$m" \
    || curl -fsSL -o "$m" "https://mibs.pysnmp.com/asn1/$m"
done
cd -
```
Expected: 目录下出现 8 个标准 MIB 文件。

- [ ] **Step 2: 验证可被解析**

```bash
uv run python -c "
from pysnmp.smi import builder, view, compiler
b = builder.MibBuilder()
compiler.add_mib_compiler(b, sources=['file://$(pwd)/src/hwtransmib/kernel/standard_mibs'])
b.load_modules('IF-MIB', 'IP-MIB')
print('standard mibs ok')
"
```
Expected: 输出 `standard mibs ok`。

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: bundle standard MIB library (SNMPv2-*, IF/IP/TCP/UDP-MIB)"
```

### Task 9.2: 全量测试 + 覆盖率检查

- [ ] **Step 1: 运行全部测试**

Run: `uv run pytest -v`
Expected: 全部 passed。

- [ ] **Step 2: 内核层覆盖率检查**

Run: `uv run pytest tests/kernel/ --cov=hwtransmib/kernel --cov-report=term-missing`
Expected: 内核层总覆盖率 ≥ 90%。若有未覆盖分支,补充测试用例。

- [ ] **Step 3: Commit(若有新增测试)**

```bash
git add -A
git commit -m "test: improve kernel coverage to ≥90%"
```

---

## 阶段 10:打包(可选,最后做)

### Task 10.1: PyInstaller 打包配置

- [ ] **Step 1: 添加 pyinstaller 依赖**

```bash
uv add --dev pyinstaller
```

- [ ] **Step 2: 创建打包脚本 build.sh**

```bash
cat > build.sh <<'EOF'
#!/usr/bin/env bash
set -e
uv run pyinstaller --noconfirm \
  --name hwtransmib \
  --windowed \
  --add-data "src/hwtransmib/kernel/standard_mibs:hwtransmib/kernel/standard_mibs" \
  --collect-all PySide6 \
  src/hwtransmib/ui/app.py
EOF
chmod +x build.sh
```

- [ ] **Step 3: 执行打包**

```bash
./build.sh
```
Expected: `dist/hwtransmib.app`(macOS)/ `dist/hwtransmib.exe`(Windows)生成。macOS 上双击可启动。

- [ ] **Step 4: Commit**

```bash
git add build.sh
git commit -m "build: add PyInstaller packaging script"
```

---

## 自审清单(完成所有任务后)

实现完所有任务后,对照规格逐条核对:

- [ ] 规格第 3 节 UI 布局:树为主、详情折叠 → Task 8.5 MainWindow
- [ ] 规格第 4 节 数据模型 → Task 1.1 + 3.1
- [ ] 规格第 5 节 OID 构造(标量/单列/多列) → Task 4.1
- [ ] 规格第 6 节 搜索(实时模糊+跳转) → Task 5.1 + 7.3 + 8.4
- [ ] 规格第 7 节 持久化(4 文件) → Task 6.1 + 6.2
- [ ] 规格第 8 节 错误处理(不崩溃) → 各 service 的错误收集 + MainWindow 的 QMessageBox
- [ ] 规格第 9 节 测试分层 → 内核 pytest、UI pytest-qt
- [ ] 规格第 10 节 uv + PySide6 + pysnmp + PyInstaller → Task 0.1 + 10.1
- [ ] 规格第 11 节 验收标准 1-8 → 端到端手动验证

**端到端手动验收脚本(规格第 11 节):**
1. `uv run hwtransmib` 启动
2. 点「导入 MIB」选 IF-MIB → 树显示
3. 点 ifDescr → 属性面板显示正确 OID/SYNTAX
4. 搜索框输入 "ifDescr" → 跳转
5. 选中 sysUpTime 标量 → 构造出 `.0` 结尾
6. 选中 ifDescr 列 → 输入 ifIndex=5 → 构造出 `...1.2.5`
7. 收藏 ifTable,构造一个 OID,关闭重开 → 数据保留
8. 详情区折叠/展开正常

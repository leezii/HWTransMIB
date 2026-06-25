# HWTransMIB — SNMP MIB 浏览与 OID 构造工具 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-25
- **作者**: 架构设计 (brainstorming 产出)

## 1. 项目概述

### 1.1 目标

跨平台桌面应用,让用户导入 SNMP MIB 文件,解析后以树形结构浏览 MIB 层次关系,查看任意节点的属性,通过名称或 OID 快速查找节点,最终**对选中节点交互式输入参数,构造出完整的 OID 访问字符串**。

### 1.2 范围边界

| 在范围内 | 不在范围内 |
|---|---|
| 导入/解析 MIB 文件 | 实际 SNMP 报文操作 (GET/SET/Walk/Trap) |
| 树形结构浏览 | SNMP Agent 连接、认证配置 |
| 节点属性查看 | 远程设备轮询/监控 |
| 名称/OID 搜索 | MIB 文件编辑 |
| OID 字符串构造(含表索引) | 批量 OID 导出 |

### 1.3 核心需求决策(已与用户确认)

| 维度 | 决策 |
|---|---|
| 应用形态 | Python 原生桌面 GUI (PySide6) |
| 最终目标深度 | 仅构造 OID 字符串,不做 SNMP 操作 |
| 参数交互范围 | 支持表索引列(整数/字符串/IP/MAC,含多列复合) |
| MIB 依赖处理 | 多文件 + 自动依赖解析 |
| 公共 MIB 库 | 内置常用标准 MIB (SNMPv2-SMI/TC、IF-MIB 等) |
| 属性面板 | 键值对表格 |
| 搜索 | 实时模糊匹配名称/OID + 跳转到树节点 |
| 持久化 | 导入列表 + OID 构造历史 + 节点收藏 |
| 解析内核 | 方案 A: PySMI + PySnmp (`pysnmp-lextudio`) |
| 环境管理 | uv |

## 2. 整体架构

四层单向依赖架构。上层依赖下层,杜绝循环依赖。

```
┌─────────────────────────────────────────────────────────────┐
│  UI 层  (PySide6 / Qt Widgets)                              │
│  MainWindow · MibTreeView · PropertyPanel · SearchBox       │
│  OidBuilderDialog · FavoritesView · HistoryView             │
└──────────────────────────┬──────────────────────────────────┘
                           │ 调用服务/订阅信号
┌──────────────────────────┴──────────────────────────────────┐
│  应用服务层  (Application Services)                          │
│  ImportService · SearchService · OidBuildService             │
└──────────────────────────┬──────────────────────────────────┘
                           │ 查询/操作领域模型
┌──────────────────────────┴──────────────────────────────────┐
│  MIB 内核层  (Mib Kernel) — 纯 Python, 无 Qt 依赖            │
│  MibParser · MibTree · MibNode · StandardMibLib · IndexBuilder│
└──────────────────────────┬──────────────────────────────────┘
                           │ 读写
┌──────────────────────────┴──────────────────────────────────┐
│  持久化层  (Persistence)                                     │
│  JsonStore                                                   │
└─────────────────────────────────────────────────────────────┘
```

### 设计原则

- **内核无 Qt 依赖**:MIB 内核层是纯 Python,可脱离 GUI 独立测试和复用。
- **单向依赖**:UI → 服务 → 内核 → 持久化。
- **服务层解耦**:UI 只和服务打交道,不直接碰 PySnmp 复杂 API。
- **分层测试**:内核层用 pytest 测,UI 层用 pytest-qt 测。

## 3. UI 布局

采用 **MIB 树为主、详情按需折叠** 的上下布局。

### 3.1 布局结构

**默认状态(折叠)**:MIB 树占满整个工作区,为浏览大型 MIB 树提供充足空间。

```
┌─────────────────────────────────────────────┐
│ 🌲 | 导入 | [🔍搜索]            | [📋 详情]  │  ← 顶部工具栏
├─────────────────────────────────────────────┤
│                                             │
│         MIB 树 (占满整个工作区)              │
│                                             │
└─────────────────────────────────────────────┘
```

**展开状态**:上下分割,下半区显示属性面板 + 辅助 Tab。

```
┌─────────────────────────────────────────────┐
│ 🌲 | 导入 | [🔍搜索]            | [📋 详情 ▦]│  ← 按钮高亮
├─────────────────────────────────────────────┤
│   MIB 树 (上半区, 仍占多数空间)              │
├──────────────────────┬──────────────────────┤
│  属性面板            │ [★收藏][🕑历史][🔧构造]│
│  键值对表格          │  右栏三 Tab           │
└──────────────────────┴──────────────────────┘
```

### 3.2 组件清单

| 组件 | 职责 |
|---|---|
| MainWindow | 顶层窗口,容纳 QSplitter、工具栏、状态栏 |
| MibTreeView | MIB 树视图(QTreeView + QStandardItemModel) |
| PropertyPanel | 属性面板,键值对表格 |
| SearchBox | 顶部搜索框,实时过滤 |
| OidBuilderDialog | OID 构造对话框/面板 |
| FavoritesView / HistoryView | 右栏收藏/历史 Tab |
| StatusBar | 底部状态栏(加载 MIB 数、节点数、就绪状态) |

### 3.3 节点图标语义

| 图标 | 节点类型 | 可构造 OID |
|---|---|---|
| 📦 | MODULE (MIB 模块根) | 否 |
| 📁 | SUBTREE (中间子树) | 否 |
| 🟢 | SCALAR (标量) | 是(自动加 `.0`) |
| 🔴 | TABLE (表对象) | 否 |
| 🔴 | ROW (表行 entry) | 否 |
| 🟢 | COLUMN (表列对象) | 是(填索引) |
| 🔖 | 收藏标记 | 叠加在上述图标上 |

### 3.4 交互细节

- **详情区默认隐藏**:工具栏「📋 详情」按钮切换显示/隐藏。
- **快速展开**:双击树节点 / 选中节点按空格,自动弹出详情区。
- **上下 QSplitter 可拖拽**:用户可自行调整比例(如树 80% / 详情 20%)。
- **OID 内联显示**:树节点旁显示 OID(根节点完整 OID,深层节点短 OID)。
- **右键上下文菜单**:树节点右键 → 构造 OID / 复制 OID / 收藏 / 复制名称。
- **状态记忆**:折叠/展开状态、分割比例持久化。

## 4. 数据模型与解析管线

### 4.1 解析管线

```
用户选择 N 个 .mib 文件
        │
        ▼
1. 文件收集 + 扫描内置标准库
        │
        ▼
2. MibParser 解析 (委托 PySnmp MibBuilder)
   · addMibSource(内置库路径)
   · loadModules(用户MIB)  ← PySnmp 自动拓扑排序补依赖
        │
        ▼
3. MibTree 构建 (遍历 MibBuilder 产物 → 生成 MibNode 树)
   · 每个 OID 段建一个节点,计算父子关系
   · 标注节点类型,反查 INDEX 定义
        │
        ▼
4. 索引服务 (名称哈希表 + OID Trie)
   O(1) 按名称/OID 查找,支持模糊搜索 + OID 精确定位
        │
        ▼
   发信号: treeReady(MibTree) → UI 渲染
```

### 4.2 领域模型 (MibKernel, 纯 Python dataclass)

```python
@dataclass
class MibNode:
    oid: str                     # 完整 OID,如 "1.3.6.1.2.1.2.2.1.2"
    name: str                    # 如 "ifDescr"
    node_type: NodeType          # MODULE / SUBTREE / SCALAR / TABLE / ROW / COLUMN
    syntax: str | None           # 如 "DisplayString (255)"
    access: str | None           # "read-only" / "read-write" / "not-accessible"
    status: str | None           # "current" / "deprecated"
    description: str | None      # 原始描述文本
    units: str | None
    parent: MibNode | None       # 父节点引用
    children: list[MibNode]      # 子节点列表(树结构)
    module_name: str             # 所属 MIB 模块名,如 "IF-MIB"
    index_specs: list[IndexSpec] | None  # 仅 TABLE/ROW 节点相关

@dataclass
class IndexSpec:
    column_name: str             # 如 "ifIndex"
    column_oid: str              # 如 "1.3.6.1.2.1.2.2.1.1"
    implied: bool                # 是否 IMPLIED 索引
    syntax: str                  # 索引值类型 → 决定输入控件

class NodeType(Enum):
    MODULE = "module"            # 📦 MIB 模块根
    SUBTREE = "subtree"          # 📁 中间子树节点
    SCALAR = "scalar"            # 🟢 标量(0 索引, OID 固定)
    TABLE = "table"              # 🔴 表对象
    ROW = "row"                  # 🔴 表行(entry)
    COLUMN = "column"            # 🟢 表列对象(可构造)
```

### 4.3 关键设计点

- **OID 驱动的树**:树按 OID 数字段组织(`iso → org → dod → internet → ...`),与 SNMP 真实层级一致。模块名仅作为节点属性。
- **node_type 是核心**:决定节点能否构造 OID —— `SCALAR` 和 `COLUMN` 可构造,`SUBTREE/TABLE/ROW` 是结构节点。UI 据此显示图标 + 灰显「构造」按钮。
- **index_specs 反查**:COLUMN 节点通过所属 ROW 反查到完整索引列定义。
- **双重索引**:名称哈希表 + OID Trie,保证大 MIB(上万节点)下搜索/跳转 O(1)~O(深度)。
- **只读快照**:解析完成后 MibNode 视为只读,UI 不直接修改。

## 5. OID 构造交互(核心)

### 5.1 构造场景

根据 `node_type` 自动切换表单:

| 场景 | 节点类型 | 交互 | 示例 |
|---|---|---|---|
| 标量 | SCALAR | 无输入,自动加 `.0` | `1.3.6.1.2.1.1.1`**.0** |
| 单列表列 | COLUMN | 填一个索引值,实时拼接 | `...1.2`**.5** |
| 多列表列 | COLUMN | 多列按声明顺序拼接 | `...1.2`**.1.192.168.1.1** |

### 5.2 SNMP 索引编码规则 (OidBuildService)

| 索引类型 | 编码规则 | 示例 |
|---|---|---|
| INTEGER | 直接十进制 | `5` |
| OCTET STRING / DisplayString | 长度前缀 + ASCII | `"abc"` → `3.97.98.99` |
| IpAddress | 点分四段 | `192.168.1.1` → `192.168.1.1` |
| PhysAddress (MAC) | 冒号转点(hex) | `00:11:22` → `0.17.34` 或 hex 形式 |
| IMPLIED STRING | 省略长度前缀 | 若 INDEX 标记 IMPLIED |

### 5.3 交互特性

- **实时预览**:输入框每次变化即时重算,高亮变更段(如 `.5`)。
- **类型感知输入控件**:INTEGER 数字框 / IpAddress 格式框 / MAC 框。
- **输入校验**:INTEGER 非数字报错;IpAddress 格式非法红框提示;校验通过才允许复制。
- **构造历史**:每次复制自动存入历史(时间戳 + 完整 OID + 节点名),右栏 Tab 可回溯。

## 6. 搜索

### 匹配维度

- 名称(不区分大小写子串)
- OID 数字串(如 "2.2.1.2")
- DESCRIPTION 关键词

### 交互

- **200ms 防抖**:输入停止后触发搜索,避免大库卡顿。
- **跳转**:回车/点击结果 → 树自动展开到该节点并高亮选中。

## 7. 持久化

存储位置:`~/.hwtransmib/`

```
~/.hwtransmib/
├── config.json          # UI 状态: 窗口尺寸 / 分割比例 / 详情区显隐
├── imports.json         # 已导入 MIB 文件路径列表(下次启动自动重载)
├── favorites.json       # 收藏节点 (oid, name, module, 添加时间)
└── history.json         # OID 构造历史 (上限 200 条, 超出 LRU 淘汰)
```

**策略**:原子写入(写临时文件 → rename),避免崩溃损坏。启动时若 JSON 损坏则备份后重置。

## 8. 错误处理

核心原则:**不崩溃,部分失败不影响其余操作**。

| 错误场景 | 处理 |
|---|---|
| MIB 解析失败(语法错误) | 定位行号,弹错误对话框列出出错 MIB + 原因,跳过该文件继续解析其余 |
| 依赖缺失 | 提示缺哪个 MIB,建议用户补充或检查内置库 |
| OID 构造输入非法 | 输入框红框 + 行内提示,禁用复制按钮 |
| 文件读取失败 | 列表逐文件报告,不中断整体导入 |
| 持久化损坏 | 备份损坏文件,重置为默认,启动继续 |

## 9. 测试策略

分层测试,逻辑复杂度集中在内核层。

| 层级 | 工具 | 重点 |
|---|---|---|
| **内核层** | pytest | ★ 重点,覆盖率 ≥ 90%:MibParser(用真实 MIB 如 IF-MIB 验证)、OID 构造引擎各类型编码(含 IMPLIED/多列)、搜索索引 |
| 服务层 | pytest | 导入流程、持久化读写(mock 文件系统) |
| UI 层 | pytest-qt | 关键交互:节点选择 / 表单提交 / 复制 |

## 10. 技术栈与打包

| 项 | 选择 |
|---|---|
| 语言 | Python ≥ 3.10 (dataclass / match-case) |
| 环境管理 | **uv** |
| UI 框架 | PySide6 (Qt 官方 Python 绑定, LGPL) |
| MIB 解析 | `pysnmp-lextudio` + `pysmi-lextudio` (活跃维护分支,支持 Py3.12) |
| 测试 | pytest + pytest-qt |
| 打包 | PyInstaller → 单文件可执行, Windows/macOS/Linux 三平台(内置 MIB 资源随包) |

## 11. 验收标准

1. 能导入多个 MIB 文件,自动解析依赖(含内置标准库),生成可浏览的 OID 树。
2. 点击树节点,属性面板正确显示 OID、SYNTAX、ACCESS、STATUS、DESCRIPTION 等。
3. 搜索框输入名称片段或 OID 子串,实时过滤并跳转到树节点。
4. 选中标量节点,一键生成 `...<oid>.0`。
5. 选中表列节点,按 INDEX 定义交互输入索引值,实时生成正确编码的完整 OID(含多列复合索引、IMPLIED)。
6. 收藏节点、查看 OID 构造历史,重启应用后数据保留。
7. 详情区可折叠/展开,比例可调,状态记忆。
8. MIB 解析失败/依赖缺失时不崩溃,给出清晰错误提示。

# HWTransMIB UI 三项优化 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-26
- **基础分支**: `feat/mib-explorer-implementation`
- **背景**: 试运行后发现三个体验优化点,均为 UI 层小改动,无新功能

## 1. 优化目标

| 编号 | 问题 | 目标 |
|---|---|---|
| OPT-1 | 导入后只展开 1 层,常用节点(如 `1.3.6.1.4.1.2011.2.25`)需多次手动展开 | 记忆用户上次展开状态,重启/重导入后自动恢复 |
| OPT-2 | 树的两列(节点名/OID)默认均分,OID 经常被截断 | 节点:OID 按 2:1 比例显示,且记忆用户拖拽后的列宽 |
| OPT-3 | 应用无图标,macOS Dock 显示默认 Python/Qt 图标 | 提供树主题应用图标,窗口与任务栏均显示 |

## 2. OPT-1: 树展开状态记忆

### 现状

`main_window.py` 两处用 `self._tree.expandToDepth(1)`(导入后、自动重载后),写死展开深度。用户每次都要手动展开到常用设备节点路径。

### 方案

- **实时维护**: 树的 `expanded` / `collapsed` 信号连接到处理函数,实时维护内存中的"已展开节点 OID 集合"。
- **恢复**: 启动/重新导入构建树后,遍历记录的 OID 列表,用 `MibTreeModel.index_from_oid(oid)` 取 QModelIndex,逐个 `setExpanded(idx, True)`。**容错**: 若某 OID 在当前树中不存在(换了设备),静默跳过。
- **首次回退**: 无历史记录时,展开到 `expandToDepth(2)`(比现在的 1 略深,改善默认体验)。
- **落盘**: `closeEvent` 时把内存集合转为 OID 列表,写入 `config.json` 的 `expanded_oids` 字段。

### 数据流

```
用户展开节点 → expanded 信号 → _on_expanded(node) → _expanded_oids.add(oid)
用户折叠节点 → collapsed 信号 → _on_collapsed(node) → _expanded_oids.discard(oid)
关闭应用    → closeEvent → config["expanded_oids"] = list(_expanded_oids)
启动/重导入  → _restore_expanded_state() → 遍历 OIDs → setExpanded
```

## 3. OPT-2: 列宽 2:1 + 记忆

### 现状

`QTreeView` 默认两列均分,无任何 `setColumnWidth` / `setSectionResizeMode` 配置。节点名通常短,OID 长,均分导致 OID 被截断。

### 方案

- **初始比例**: 树创建后,设置表头为 `Interactive`(允许用户拖拽调整),并按 **2:1** 设定初始列宽。基于树的当前宽度计算:`w0 = width * 2 // 3`,`w1 = width - w0`。
- **resizeEvent 同步**: 树宽度变化时,若用户未手动调整过列宽,保持 2:1 比例;用户手动拖拽过后则固定用户值(用一个 `_column_widths_user_set` 标志区分)。
- **记忆**: 把两列宽度写入 `config.json` 的 `tree_column_widths` 字段。启动时恢复;首次无记录用 2:1 默认。

### 涉及组件

- `MainWindow._build_ui` 中树初始化后追加列宽配置
- `MibTreeModel` 无需改动(纯 view 层调整)

## 4. OPT-3: 应用图标(树主题)

### 现状

`app.py` 未调用 `setWindowIcon`,项目无图标资源。macOS Dock 显示通用图标。

### 方案

- **资源**: 在 `src/hwtransmib/ui/resources/` 目录放置树主题 PNG 图标 `app-icon.png`(建议 256x256 或更大,含透明背景,体现"🌲 MIB 树"概念)。
- **加载**: `app.py` 用 `importlib.resources.files()` 定位图标(兼容源码运行与 PyInstaller 打包),`app.setWindowIcon(QIcon(...))`。
- **覆盖范围**:
  - 窗口标题栏图标 ✓
  - 任务栏图标 ✓(Linux/Windows)
  - macOS Dock:窗口图标在运行时生效;**Dock 持久图标需 `Info.plist`**,留到 Task 10.1 打包阶段处理
- **MainWindow**: 也设 `self.setWindowIcon(...)` 双保险(部分平台 Qt 行为差异)。

### 资源打包

`pyproject.toml` 的 `force-include` 已含 standard_mibs;图标资源需同样加入打包配置,确保 PyInstaller/uv build 包含。

## 5. 持久化数据结构变化

`config.json` 新增字段(向后兼容,旧配置无这些字段时用默认值):

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `expanded_oids` | `list[str]` | `[]` | 已展开节点的完整 OID 列表 |
| `tree_column_widths` | `list[int]` | `null` | 树两列宽度 `[节点宽, OID宽]`,null 表示用 2:1 默认 |

`UserData` 的默认 config 模板需补充这两个字段。

## 6. 测试策略

| 优化项 | 测试方式 |
|---|---|
| OPT-1 展开/折叠记忆 | 单元测试:模拟 expanded/collapsed 信号,验证集合维护;验证恢复时跳过不存在的 OID |
| OPT-2 列宽 | 冒烟测试:验证树初始化后列宽比例;验证持久化读写 |
| OPT-3 图标 | 冒烟测试:验证 `setWindowIcon` 被调用且图标资源存在(不依赖 GUI 渲染) |

用 pytest-qt 的 `qtbot` 模拟信号。内核层无改动,无需新增内核测试。

## 7. 涉及文件

| 文件 | 改动 |
|---|---|
| `src/hwtransmib/ui/main_window.py` | 树展开记忆、列宽 2:1 + 持久化、setWindowIcon |
| `src/hwtransmib/ui/app.py` | app.setWindowIcon + 图标资源加载 |
| `src/hwtransmib/ui/resources/app-icon.png` | 新增树主题图标 |
| `src/hwtransmib/persistence/user_data.py` | config 默认值补充 expanded_oids/tree_column_widths |
| `pyproject.toml` | force-include 加入 ui/resources |
| `tests/ui/test_main_window_state.py` | 新增状态记忆测试 |

## 8. 验收标准

1. 导入华为 OPTIX MIB 后,手动展开到 `1.3.6.1.4.1.2011.2.25`,关闭重开应用 → 该节点仍展开。
2. 切换导入其他设备 MIB(不含上述 OID)→ 不报错,已记忆但树中不存在的 OID 静默跳过。
3. 树的节点列宽度约为 OID 列的 2 倍;拖拽调整列宽后,关闭重开仍保持用户调整值。
4. 应用启动后,窗口标题栏显示树主题图标。
5. 全部既有测试(92 个)仍通过。

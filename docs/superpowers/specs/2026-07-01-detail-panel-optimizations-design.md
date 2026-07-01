# 详情区三项优化 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-07-01
- **基础分支**: `main`
- **背景**: 试运行后发现详情区(属性面板 ↔ 收藏/历史 Tab)三个体验问题:分隔宽度写死不可调、历史记录缺失索引值、收藏/历史表列宽未配置导致 OID 被压缩截断。均为 UI 层 + 持久化层改动,无 kernel 改动。

## 1. 优化目标

| 编号 | 问题 | 目标 |
|---|---|---|
| DET-1 | 详情区内部(属性 ↔ 收藏/历史)用 `QHBoxLayout` 固定 stretch(3:2),无手柄,宽度不可调 | 改为可拖动的水平 `QSplitter`,并持久化比例 |
| DET-2 | `build_and_record()` 接收了 `index_values` 却未写入 history entry,历史只记了构造出的 OID 和节点名,缺索引明细 | 历史记录补充索引值,显示为 `节点名 = 值`(联合索引每组一行) |
| DET-3 | 收藏表(2 列)、历史表(3 列)创建后无任何列宽/header resize 配置,QTableWidget 默认均分导致 OID 列被压缩 | 配置 Interactive header + 持久化列宽,合理默认比例 |

## 2. 架构与数据流

三个优化点全部落在 UI 层与持久化层,不涉及 kernel。沿用项目已有的"config.json 键 + 启动读取 / 关闭写入"惯例(参考现有 `split_sizes`、`tree_column_widths`、`expanded_oids`)。

`config.json` 新增 4 个键(均向后兼容,旧 config 无这些键时用默认值):

| 配置键 | 类型 | 默认回退 | 用途 |
|---|---|---|---|
| `detail_split_sizes` | `list[int]` \| `None` | 按窗口宽 6:4 | 详情区水平 splitter 比例 |
| `fav_column_widths` | `list[int]` \| `None` | 按表宽比例分配 | 收藏表 2 列宽度 |
| `hist_column_widths` | `list[int]` \| `None` | 按表宽比例分配 | 历史表 4 列宽度(原 3 列 + 新增"索引"列) |

数据流:

```
写入索引值:  OidBuilderDialog._copy() → OidBuildService.build_and_record(node, index_values)
             → entry["index_values"] = dict(index_values) → UserData.add_history_entry() → history.json
渲染索引值:  MainWindow._refresh_history() → 读 entry["index_values"] → _format_index() 多行 → "索引"列单元格
分隔条持久化: 启动 _apply_detail_split() 读 config["detail_split_sizes"];closeEvent → 写回
列宽持久化:  启动 _apply_fav_column_widths()/_apply_hist_column_widths() 读 config;closeEvent → 写回
```

## 3. DET-1: 详情区可调节分隔条

### 现状

`main_window.py` `_build_detail()`(第 153–170 行)详情区内部用 `QHBoxLayout` + 固定 stretch:

```python
layout.addWidget(self._property, 3)   # 属性面板 stretch=3(固定)
layout.addWidget(self._tabs, 2)       # Tab 区 stretch=2(固定)
```

无任何手柄,用户无法拖动调节。对比:外层(树 ↔ 详情区)已是真正的 `QSplitter`(第 91–106 行)并已持久化(`config.json["split_sizes"]`),可作为现成模板。

### 方案

把详情区内部 `QHBoxLayout` 包装改为 `QSplitter(Qt.Orientation.Horizontal)`:

```python
splitter = QSplitter(Qt.Orientation.Horizontal)
splitter.addWidget(self._property)   # 属性面板
splitter.addWidget(self._tabs)       # 收藏/历史 Tab 区
box_layout = QHBoxLayout(box)
box_layout.setContentsMargins(4, 4, 4, 4)
box_layout.addWidget(splitter)
self._detail_splitter = splitter
```

- **最小宽度**:`self._property.setMinimumWidth(200)`、`self._tabs.setMinimumWidth(240)`,避免极窄窗口下被压到不可见。
- **启动恢复**:新增 `_apply_detail_split()` 读 `config["detail_split_sizes"]`,长度为 2 且两值均正则用记录值;否则按详情区当前宽度 6:4(属性区略宽,承载表格)。
- **持久化**:`closeEvent` 里把 `self._detail_splitter.sizes()` 写入 `config["detail_split_sizes"]`(仿现有 `split_sizes` 第 432 行做法)。

### 涉及组件

- `MainWindow._build_detail`(详情区内部布局改造)
- `MainWindow._apply_detail_split`(新增,启动恢复)
- `MainWindow.closeEvent`(新增写回逻辑)

## 4. DET-2: 历史记录补充索引值

### 现状

唯一写入点 `OidBuildService.build_and_record()`(`services/oid_build_service.py` 第 37–47 行)接收了 `index_values`(`dict[str, str]`,如 `{"ifIndex": "5"}`)却未存入 entry:

```python
self._ud.add_history_entry({
    "oid": oid,
    "name": node.name,
    "module": node.module_name,
    "timestamp": int(time.time()),
})  # index_values 没有被记录!
```

历史渲染 `_refresh_history()`(第 407–421 行)按 3 列填充(时间 / OID / 节点),无索引信息。

### 方案

**写入**(entry 增加字段):

```python
self._ud.add_history_entry({
    "oid": oid,
    "name": node.name,
    "module": node.module_name,
    "index_values": dict(index_values),  # 新增:如 {"ifIndex": "5"}
    "timestamp": int(time.time()),
})
```

存储层 `UserData.add_history_entry()` 无需改 schema —— entry 是自由 dict,LRU 去重仍按 `oid` 匹配,不受影响。

**渲染**(历史表 3 列 → 4 列):

历史表表头由 `["时间", "OID", "节点"]` 改为 `["时间", "OID", "节点", "索引"]`。新增"索引"列格式化逻辑:

```python
def _format_index(values: dict[str, str]) -> str:
    """索引值格式化:联合索引每组一行,形如 'ifIndex = 5'。"""
    if not values:
        return ""
    return "\n".join(f"{k} = {v}" for k, v in values.items())
```

- 单值索引 → 一行 `ifIndex = 5`。
- 联合索引 → 多行,每组 `节点名 = 值` 一行,如 `ifIndex = 5\nifDescr = eth0`。
- 标量节点(无索引)→ "索引"列留空。
- 单元格多行显示:设 `QTableWidget` 的 `setWordWrap(True)`,并在填充后 `resizeRowsToContents()` 让行高自适应。
- TC 枚举值:用户填入的文本(枚举名或数字)原样显示,不做二次解析。

### 索引格式约定

用户确认:左侧用**节点名**(非完整数字 OID),可读性最好。如 `ifIndex = 5`,而非 `1.3.6.1.2.1.2.2.1.1 = 5`。

### 涉及组件

- `OidBuildService.build_and_record`(entry 加 `index_values` 字段)
- `MainWindow._refresh_history`(历史表 3→4 列,填充"索引"列)
- `MainWindow._build_detail`(历史表列数 3→4)
- 新增 `MainWindow._format_index`(静态/模块级辅助函数)

## 5. DET-3: 收藏/历史表列宽可调与持久化

### 现状

收藏表(2 列)、历史表(原 3 列)创建后**完全没有配置** header resize 模式或列宽,既无 `setColumnWidth`、也无 `setSectionResizeMode`、也没关闭 `setStretchLastSection`。QTableWidget 用默认 header 行为(均分),导致 OID 列(通常最长)与"时间""节点"列等宽被压缩。

对比:树视图(`_apply_column_widths()` 第 213–233 行)有完整的 Interactive + 持久化 + 2:1 默认分配,是现成可复用的模板。

### 方案

为收藏表(2 列)、历史表(4 列,含新增"索引"列)分别配置 header,复用树的"Interactive + 持久化 + 默认比例回退"模式:

```python
def _apply_table_column_widths(table, saved_widths, defaults_ratio, total_width):
    """通用列宽应用:Interactive 模式 + 持久化 + 默认比例回退。"""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setStretchLastSection(False)
    if (saved_widths and len(saved_widths) == len(defaults_ratio)
            and all(w > 0 for w in saved_widths)):
        for col, w in enumerate(saved_widths):
            table.setColumnWidth(col, w)
    else:
        for col, ratio in enumerate(defaults_ratio):
            table.setColumnWidth(col, int(total_width * ratio))
```

- **默认比例**(按内容长度经验值,首次无记录时按表可视宽度分配):
  - 收藏表(2 列):`[节点 0.55, OID 0.45]`
  - 历史表(4 列):`[时间 0.15, OID 0.35, 节点 0.20, 索引 0.30]`
- **持久化**:`closeEvent` 分别写 `config["fav_column_widths"]` / `config["hist_column_widths"]`。
- **启动时机**:由于表格初始可视宽度可能为 0(尚未显示),应用列宽需在窗口显示后或 `showEvent` 触发;参照 `_apply_column_widths()` 用 `max(viewport().width(), 600)` 兜底。

### 涉及组件

- `MainWindow._build_detail`(两个表格创建后保留引用)
- `MainWindow._apply_fav_column_widths` / `_apply_hist_column_widths`(新增,或合并为一个通用方法)
- `MainWindow.closeEvent`(新增写回逻辑)

## 6. 持久化数据结构变化

`config.json` 新增字段(均向后兼容,旧 config 无这些字段时用默认值):

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `detail_split_sizes` | `list[int]` \| `None` | `null` | 详情区水平 splitter 两 widget 宽度 `[属性宽, Tab宽]`,null 表示用 6:4 默认 |
| `fav_column_widths` | `list[int]` \| `None` | `null` | 收藏表 2 列宽度 `[节点宽, OID宽]`,null 表示按比例默认 |
| `hist_column_widths` | `list[int]` \| `None` | `null` | 历史表 4 列宽度 `[时间宽, OID宽, 节点宽, 索引宽]`,null 表示按比例默认 |

`history.json` 的 entry 结构增加字段(entry 是自由 dict,无需 schema 迁移):

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `index_values` | `dict[str, str]` | `{}` | 用户填入的索引值 `{列名: 值}`。旧记录无此字段,读取时 `.get("index_values", {})` 兜底 |

`UserData.__init__` 的 config 默认模板(第 23–29 行)需补充上述 3 个新键。

## 7. 错误处理与边界情况

### 索引值边界

- `index_values` 为空 dict(标量节点)→ entry 存 `"index_values": {}`,渲染时"索引"列留空。
- `index_values` 缺失(旧历史记录,升级前已存的 entry 无此字段)→ `_refresh_history()` 用 `entry.get("index_values", {})` 兜底,留空不报错。**向后兼容,旧记录无需迁移**。
- TC 枚举值(值字段存的是用户填入的文本,可能是枚举名或数字)→ 原样显示,不做二次解析。

### 列宽/Splitter 边界

- 配置值为空 / 长度不匹配列数 / 含非正值 → 回退到默认比例(校验长度与正值)。
- 详情区 splitter sizes 全 0 或异常 → 按窗口宽度 6:4 重新分配。
- 窗口最小化 / 极窄时 → splitter 各 widget 设 `minimumWidth`(属性面板 ≥200px、Tab 区 ≥240px),避免被压到不可见。

### 持久化健壮性

写 config 仍走现有 `UserData` 的 JSON 序列化,失败由现有逻辑处理,不引入新风险。

## 8. 测试策略

项目现有测试结构(`tests/`),按层补测试:

| 层 | 测试内容 | 说明 |
|---|---|---|
| services 单元测试 | `OidBuildService.build_and_record()` 写入的 entry 含 `index_values` 字段且内容正确 | 不依赖 Qt,最易测 |
| services 单元测试 | 空 `index_values`(标量节点)→ 字段为空 dict | 边界 |
| persistence 单元测试 | 旧格式 entry(无 `index_values`)能被正常读取,不抛异常 | 向后兼容 |
| UI 辅助函数 | `_format_index()` 单元测试:空、单值、联合索引(多行)三种情况 | 纯函数,易测 |
| UI 手动验证清单 | 分隔条可拖动并持久化;列宽可拖动并持久化;多行索引行高自适应 | Qt GUI 测试基建不依赖,用手动清单 |

内核层无改动,无需新增内核测试。

## 9. 涉及文件

| 文件 | 改动 |
|---|---|
| `src/hwtransmib/ui/main_window.py` | 详情区改 splitter;历史表 3→4 列;两个表格列宽配置 + 持久化;`_format_index` 新增;`closeEvent` 写回 |
| `src/hwtransmib/services/oid_build_service.py` | `build_and_record()` entry 加 `index_values` 字段 |
| `src/hwtransmib/persistence/user_data.py` | config 默认模板补充 3 个新键 |
| `tests/services/test_oid_build_service.py` | 新增 index_values 写入测试 |
| `tests/persistence/test_user_data.py` | 新增向后兼容测试 |
| `tests/ui/test_main_window_state.py` | 新增 `_format_index` 单元测试 |

## 10. 验收标准

1. 详情区属性面板与收藏/历史 Tab 之间出现可拖动的分隔条,拖动后关闭重开应用 → 比例保持。
2. 在 OID 构造对话框填写索引值(如 ifIndex=5)并复制后,历史 Tab 对应记录的"索引"列显示 `ifIndex = 5`;联合索引(如 ifIndex=5, ifDescr=eth0)显示两行。
3. 标量节点(无索引)构造后,历史"索引"列留空,其他列正常。
4. 旧版本产生的历史记录(无 `index_values` 字段)在升级后仍能正常显示,不报错。
5. 收藏表、历史表各列宽度可单独拖动调节;OID 列默认占比合理(收藏 ~45%、历史 ~35%),不再被均分压缩;拖动调整后关闭重开仍保持用户值。
6. 全部既有测试仍通过(无回归)。

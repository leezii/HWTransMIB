# OID 构造对话框 TC 枚举值补全 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-30
- **基础分支**: `main`
- **背景**: 点击「构造 OID」弹出索引输入框时,索引字段类型为带枚举的 TC 定义类型(如 `InetVersion`),用户无法得知有哪些枚举值,需手工查 MIB 填数字。优化为键入少量字符即可匹配提示枚举名。

## 0. 关键探测结论(已验证)

- PySnmp syntax 对象暴露枚举:`syn.namedValues.items()` → `[("unknown",0),("ipv4",1),("ipv6",2)]`。
- PySnmp 索引编码器**接受枚举名**:`getInstIdFromIndices("ipv4", 5)` → `(1, 5)`。故"键入枚举名 → 自动编码为整数"端到端可行。
- **并非所有 TC 整数有枚举**:`InetVersion`/`ifAdminStatus` 有,`InterfaceIndex` 无。无枚举的列保持普通数字输入。
- **既有约束冲突**:`tests/kernel/test_tc_integer_detection.py::test_tc_integer_rejects_enum_name` 锁定 TC 整数索引拒绝枚举名;`OidBuilder._coerce` 强制 `int(raw)`。本特性必须放开此约束。

## 1. 用户决策(已确认)

| 决策点 | 选择 |
|---|---|
| 枚举名输入处理 | **同时接受枚举名和数字**(PySnmp 原生支持枚举名编码) |
| 提示交互方式 | **QLineEdit + QCompleter**(保留现有控件,改动最小) |
| 补全器触发范围 | **有枚举值的列才提示**(含 TC 包装与原生 INTEGER-with-enums;无枚举列不挂补全器) |

## 2. 架构方案(已确认)

内核层一次性提取枚举值填入 `IndexSpec`,UI 层只消费纯数据,不触碰 PySnmp 内省。与现有 `is_integer` 提取同构,保持四层单向依赖(UI→服务→内核→持久化),内核可脱离 GUI 独立测试。

## 3. 数据提取(内核层)

**改动:`src/hwtransmib/kernel/model.py`**

`IndexSpec` 新增字段:
```python
named_values: list[tuple[str, int]] = field(default_factory=list)
# InetVersion → [("unknown",0),("ipv4",1),("ipv6",2)];空列表=无枚举
```

**改动:`src/hwtransmib/kernel/tree_builder.py`**

- `_syntax_info_of_symbol(module, name)` 扩展返回三元组 `(syntax_name, is_integer, named_values)`,从 `syn.namedValues.items()` 提取。
- `_extract_index_specs` 透传 `named_values` 到 `IndexSpec`。

提取实现要点:`syn = sym.getSyntax()`;若 `syn` 有 `namedValues` 属性且 `list(syn.namedValues.items())` 非空则填充,否则空列表。`SmiError`/异常时回退为空列表(与现有 `is_integer` 的容错一致)。

## 4. 校验与编码放开(内核层)

**改动:`src/hwtransmib/kernel/oid_builder.py`**

`_coerce(spec, raw)` 调整优先级:
```
若 spec.named_values 非空 且 raw 是合法枚举名 → 返回 raw(字符串,PySnmp 接受枚举名)
否则走原 _looks_integer → int(raw) 路径(数字输入、无枚举 TC 不变)
```

`_validate_value(spec, raw)` 同步放开:
```
若 spec.named_values 非空:
    raw 命中枚举名 → 通过
    raw 是纯数字   → 通过(数字始终接受)
    否则          → 报错"{column} 需要枚举名或数字,得到 {raw}"
否则保持原整数校验逻辑(_looks_integer)
```

**既有测试调整:**
- `test_tc_integer_rejects_enum_name` → 改名 `test_tc_integer_accepts_enum_name`,断言翻转(`InetVersion="ipv4"` 现在 `errors == []`)。
- 其余三个用例(`test_tc_integer_flag_detected` / `test_tc_integer_accepts_numeric` / `test_non_integer_tc_not_flagged`)不受影响。

数字输入路径完全不变,保证向后兼容;枚举名路径复用 PySnmp 原生能力,不引入自定义编码。

## 5. UI 补全器(UI 层)

**改动:`src/hwtransmib/ui/oid_builder_dialog.py`**

`_build_ui` 中,仅对 `spec.named_values` 非空的列挂补全器:
```python
from PySide6.QtWidgets import QCompleter
from PySide6.QtCore import Qt

labels = [f"{name} ({val})" for name, val in spec.named_values]
completer = QCompleter(labels, edit)
completer.setCaseSensitivity(Qt.CaseInsensitive)
completer.setFilterMode(Qt.MatchContains)   # 键入少量字符即可匹配
edit.setCompleter(completer)
```

候选项格式 `"ipv4 (1)"`:名称在前便于键入匹配,数字便于核对。

**填入值规范化(`_values()` 调用处):** 新增 `_normalize(spec, text)` 辅助,仅对有枚举的列生效:
```
文本形如 "name (n)" → 返回 "name"(枚举名交内核编码)
纯数字 "5"          → 原样返回(数字路径)
裸枚举名 "ipv4"     → 原样返回(用户只键入未选下拉)
```
其余列直接返回 text。预览 `_refresh`、复制 `_copy` 通过 `_values()` 拿到规范化值后仍走 `service.validate/build`,复用第 4 节放开后的内核逻辑,零侵入。

**不变项:** 实时预览、复制历史逻辑不变;无枚举列(`InterfaceIndex`)无补全器,行为同今天。

## 6. 测试策略

### 内核层(`tests/kernel/`)

| 场景 | 文件 | 断言 |
|---|---|---|
| `named_values` 正确提取 | `test_tc_integer_detection.py` | `ipIfStatsIPVersion`(InetVersion)`named_values == [("unknown",0),("ipv4",1),("ipv6",2)]` |
| 无枚举 TC 不提取 | 同上 | `ipIfStatsIfIndex`(InterfaceIndex)`named_values == []` |
| 枚举名通过校验 | 同上 | `InetVersion="ipv4"` → `validate` 返回 `[]`(翻转既有用例) |
| 枚举名正确编码 | `test_oid_builder.py` | `InetVersion="ipv4", InterfaceIndex=5` → `build()` 含 `.1.5` 后缀 |
| 数字仍可编码 | 同上 | `InetVersion="1"` → 结果同上(数字路径不变) |
| 非法枚举名报错 | 同上 | `InetVersion="foo"` → 报"需要枚举名或数字" |
| 非枚举列不受影响 | 同上 | `InterfaceIndex="abc"` → 仍报"需要整数" |

### UI 层(`tests/ui/test_oid_builder_dialog.py`)

| 场景 | 断言 |
|---|---|
| 枚举列挂了补全器 | `ipIfStatsIPVersion` 的 `QLineEdit.completer() is not None`,候选项含 `"ipv4 (1)"` |
| 非枚举列无补全器 | `ipIfStatsIfIndex` 的 `QLineEdit.completer() is None` |
| 选下拉后预览正确 | `set_index_value("ipIfStatsIPVersion", "ipv4 (1)")` + `ifIndex=5` → 预览以 `.1.5` 结尾 |
| 纯数字输入仍可用 | `set_index_value("ipIfStatsIPVersion", "1")` → 预览同上 |

UI 测试用 `dlg.set_index_value()` 注入(既有模式),通过 `_values()`/规范化验证,不模拟真实键盘补全事件(脆弱且平台相关)。

### 不变项验证

- 既有 `test_oid_builder.py` 全部(IF-MIB ifIndex 数字索引)不受影响。
- 既有 `test_oid_builder_dialog.py` 三个(scalar/column/invalid)不受影响——IF-MIB ifIndex 无枚举。

## 7. 涉及文件

| 文件 | 改动 |
|---|---|
| `src/hwtransmib/kernel/model.py` | `IndexSpec` 增 `named_values` 字段 |
| `src/hwtransmib/kernel/tree_builder.py` | `_syntax_info_of_symbol` 提取 `named_values`,透传到 `IndexSpec` |
| `src/hwtransmib/kernel/oid_builder.py` | `_coerce`/`_validate_value` 放开枚举名(仅对有枚举列) |
| `src/hwtransmib/ui/oid_builder_dialog.py` | 有枚举列挂 `QCompleter`;新增 `_normalize` 规范化填入值 |
| `tests/kernel/test_tc_integer_detection.py` | 翻转 `rejects`→`accepts`;新增 `named_values` 提取断言 |
| `tests/kernel/test_oid_builder.py` | 新增枚举名编码/数字兼容/非法名报错用例 |
| `tests/ui/test_oid_builder_dialog.py` | 新增补全器挂载与规范化预览用例 |

不改动:服务层(`oid_build_service.py` 透传,无需改)、持久化层、其他 UI。

## 8. 验收标准

1. 打开带枚举 TC 索引的列(如 `ipIfStatsInReceives`)→ 对应输入框键入字符弹出过滤后的候选列表。
2. 选中 `ipv4 (1)` 或输入 `ipv4`/`1` → 实时预览出正确 OID(以 `.1.5` 结尾)。
3. 无枚举的索引列(如 `InterfaceIndex`)→ 无候选弹出,行为同今天。
4. 全量 `uv run pytest` 通过(含翻转/新增用例)。

# HWTransMIB 属性面板显示索引构成 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-26
- **基础分支**: `feat/mib-explorer-implementation`
- **背景**: TABLE/ROW 类型节点无法查看索引构成,需在属性面板展示

## 1. 目标

让 TABLE 和 ROW 类型节点的属性面板显示其**索引构成**(哪些列构成索引、各列的 OID/类型/IMPLIED 标记),帮助用户理解 OID 构造的索引来源。

## 2. 数据来源(已就绪,无需内核改动)

- ROW 节点:`MibNode.index_specs: list[IndexSpec]`(由 MibTreeBuilder 填充)
- IndexSpec 字段:`column_name`、`column_oid`、`syntax`、`implied`

## 3. 展示规则

### ROW 节点(有 index_specs)

在现有属性表格末尾追加索引构成行:
- 每个索引列一行
- 属性列:`索引列 N`(N 从 1 开始)
- 值列:`column_name (column_oid) · syntax · [IMPLIED]`
  - IMPLIED 仅在该索引标记为 implied 时显示
- 示例:
  - `索引列 1` → `ifIndex (1.3.6.1.2.1.2.2.1.1) · INTEGER`
  - `索引列 2` → `ipNetToMediaNetAddress (...) · IpAddress · IMPLIED`

### TABLE 节点(无 index_specs,自动取子 ROW)

TABLE 节点本身无 `index_specs`。在 `show_node` 中:
- 遍历 `node.children` 找第一个 NodeType.ROW 子节点
- 用该 ROW 的 `index_specs` 显示
- 属性列标注来源:`索引构成(来自 {row_name})`,如 `索引构成(来自 ifEntry)`

### 其他节点类型

- SUBTREE / SCALAR / COLUMN / MODULE:不显示索引行(保持现状)
- ROW/TABLE 但 index_specs 为空:显示 `索引构成` → `无`

## 4. 涉及文件

| 文件 | 改动 |
|---|---|
| `src/hwtransmib/ui/property_panel.py` | `show_node` 增加索引行 + TABLE 取子 ROW 逻辑 |
| `tests/ui/test_property_panel.py` | 新增:验证 ROW/TABLE 显示索引行、SCALAR 不显示 |

不改动:内核层(model.py / tree_builder.py)、表格列结构(仍 2 列)。

## 5. 测试策略

| 场景 | 验证 |
|---|---|
| ROW 节点(IF-MIB ifEntry) | 属性表格含"索引列 1"行,值含 ifIndex + OID + INTEGER |
| 多列索引(IP-MIB ipNetToMediaEntry) | 含多个索引列行 |
| TABLE 节点(ifTable) | 显示来自子 ROW(ifEntry)的索引,标注"来自 ifEntry" |
| SCALAR 节点(sysDescr) | 无索引行(表格行数与现状一致) |
| IMPLIED 标记 | 若存在 IMPLIED 索引,值列含 "IMPLIED" |

用 pytest-qt 的 qtbot 实例化 PropertyPanel,构造 MibNode 调用 show_node,断言表格内容。

## 6. 验收标准

1. 选中 ROW 节点(如 ifEntry)→ 属性面板显示索引构成行(列名/OID/类型)。
2. 选中 TABLE 节点(如 ifTable)→ 属性面板显示来自子 ROW 的索引构成,标注来源。
3. 选中 SCALAR/SUBTREE 节点 → 不显示索引行。
4. 多列索引的 ROW(如 ipNetToMediaEntry)→ 显示所有索引列。
5. 既有 103 个测试仍通过。

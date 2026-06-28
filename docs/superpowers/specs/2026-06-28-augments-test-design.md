# AUGMENTS 增强表回归测试 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-28
- **基础分支**: `main`(v0.1.1)
- **背景**: 探测发现 PySnmp 已自动处理 AUGMENTS(增强表继承被增强表的 INDEX),功能正确,但无测试覆盖

## 1. 目标

用 IF-MIB 的 ifXTable(`AUGMENTS { ifEntry }`)锁定增强表的索引继承行为,防止未来内核重构导致退步。

## 2. 探测结论(已验证)

| 验证点 | 结果 |
|---|---|
| ifXEntry 的 `indexNames` | `((0, 'IF-MIB', 'ifIndex'),)` —— PySnmp 通过 `registerAugmentions` 自动继承 ifEntry 的索引 |
| ifXEntry 的 `index_specs` | `[IndexSpec(ifIndex, ...)]` 正确 |
| ifName(列)构造 ifIndex=5 | `1.3.6.1.2.1.31.1.1.1.18.5` 正确 |

**根因:** PySnmp 7.1 的 `registerAugmentions` 在 `load_modules` 时把被增强表的 INDEX 复制给增强表行的 `indexNames`,我们的 `_extract_index_specs` 读 `indexNames` 自然拿到正确数据。

## 3. 测试点

| 用例 | 验证 |
|---|---|
| 增强表行 ifXEntry 的 index_specs 含 ifIndex | 索引继承生效 |
| 增强表列 ifName 的 is_constructible 为 True | 可构造 |
| ifName 用 ifIndex 构造正确 OID | 端到端构造 |
| ifXTable(TABLE)属性面板显示索引(来自 ifXEntry) | UI 链路覆盖 |

## 4. 涉及文件

- 新增 `tests/kernel/test_augments.py`(纯测试)

**不改动:** 内核/UI 代码。测试数据用内置 IF-MIB(已在 `standard_mibs`)。

## 5. 验收标准

1. 4 个测试用例全部通过。
2. 既有 111 个测试不回归。
3. 覆盖率不下降。

# 中优先级优化(4 项)设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-28
- **基础分支**: `main`(含 AUGMENTS 测试)
- **背景**: v0.1.1 后的中优先级待办,4 项独立优化

## 1. 概述

| 编号 | 优化 | 类型 | 风险 |
|---|---|---|---|
| #5 | IMPLIED 索引测试覆盖 | 纯测试 | 低 |
| #6 | 历史排序(时间列) | UI | 低 |
| #4 | 搜索结果列表(下拉) | UI | 中 |
| #3 | 搜索性能(先测后定) | 性能评估 | 低 |

执行顺序:#5 → #6 → #4 → #3(从低风险到中风险,#3 最后因可能不做)。

## 2. #5 IMPLIED 索引测试覆盖

### 现状(已探测)
- `tree_builder._extract_index_specs` 已采集 `implied` 标志(`indexNames` 首元素)
- `oid_builder` 委托 PySnmp `getInstIdFromIndices`,IMPLIED 自动省略长度前缀
- **已验证正确**,但无测试覆盖

### 测试数据
新增 fixture:`tests/fixtures/mibs/SNMP-COMMUNITY-MIB`(已下载,含 `INDEX { IMPLIED snmpCommunityIndex }`)。

### 测试点
| 用例 | 验证 |
|---|---|
| snmpCommunityEntry 的 index_specs[0].implied == True | IMPLIED 标志采集 |
| snmpCommunityName 用字符串索引构造,无长度前缀 | IMPLIED 编码正确(`public` → `.112.117...` 非 `.6.112...`) |

### 涉及文件
- `tests/fixtures/mibs/SNMP-COMMUNITY-MIB`(已存在)
- 新增 `tests/kernel/test_implied_index.py`

## 3. #6 历史排序

### 现状
- `UserData.add_history_entry` 已记 `timestamp`(int 时间戳)
- 历史 Tab(`_hist_view`)2 列(OID/节点),按 LRU 插入顺序显示,timestamp 未用

### 方案
- 历史 Tab 表格改为 3 列:**时间 / OID / 节点**
- 时间格式化为可读(如 `06-28 13:05`,用 `datetime.fromtimestamp`)
- 按存储顺序(LRU,最新在前)显示——当前插入逻辑已保证最新在前,无需重排
- 表头可点击排序(可选,YAGNI 先不做)

### 涉及文件
- `src/hwtransmib/ui/main_window.py`(`_refresh_history` + `_build_detail` 的 `_hist_view` 列定义)
- `tests/ui/test_main_window_state.py`(新增历史显示测试)

## 4. #4 搜索结果列表

### 现状
- `SearchService.search` 返回匹配节点列表
- `MainWindow._on_search` 只取 `results[0]` 跳转,无结果列表呈现

### 方案
- SearchBox 下方加 `QListWidget`(搜索结果列表),`search_requested` 信号触发时填充
- 每项显示:`节点名 (OID)` + 类型图标
- 行为:
  - 实时填充(随防抖搜索结果更新)
  - 点击项 → 跳转到该节点(`_select_node`)
  - 回车 → 跳转第一项(保留原快捷)
  - 结果为空 → 列表隐藏
- 列表最大显示 8 项,超出滚动

### 涉及文件
- `src/hwtransmib/ui/search_box.py` 或 `main_window.py`(决定列表归属)
- `tests/ui/test_search_results.py`(新增)

### 设计选择:列表归属
列表逻辑上是 SearchBox 的伴随组件。但跳转需访问 MainWindow 的树。**方案:列表放 MainWindow(SearchBox 下方),由 MainWindow 接 SearchBox 信号填充**——避免 SearchBox 反向依赖 MainWindow。

## 5. #3 搜索性能(先测后定)

### 现状
- `SearchIndex.search` 全量线性扫描所有节点
- 规格原设计:名称哈希 + OID 前缀 Trie

### 方案:先做性能基准
- 用真实大 MIB(华为 OPTIX 6184 节点)测量单次搜索耗时
- 基准脚本:搜索常见词(如 "if"),测 100 次取平均
- **判断阈值:**
  - < 50ms:当前性能可接受,**不做优化**(YAGNI),规格记录结论
  - ≥ 50ms:实现名称哈希(name→nodes)+ 模糊匹配优化

### 涉及文件
- 新增 `tests/perf/bench_search.py`(基准脚本,非单元测试)
- 若需优化:改 `src/hwtransmib/kernel/search_index.py`

## 6. 涉及文件汇总

| 文件 | 改动归属 |
|---|---|
| `tests/fixtures/mibs/SNMP-COMMUNITY-MIB` | #5(已下载) |
| `tests/kernel/test_implied_index.py` | #5 新增 |
| `src/hwtransmib/ui/main_window.py` | #6 历史列 + #4 搜索列表 |
| `tests/ui/test_main_window_state.py` | #6 新增历史测试 |
| `tests/ui/test_search_results.py` | #4 新增 |
| `tests/perf/bench_search.py` | #3 新增基准 |

## 7. 验收标准
1. IMPLIED 测试:snmpCommunityEntry 的 implied 标志为 True,字符串索引构造无长度前缀。
2. 历史 Tab 显示时间列,格式可读,最新在前。
3. 搜索时下方出现结果列表,点击项可跳转,回车跳第一项。
4. 搜索性能基准产出报告;若 <50ms 则记录"无需优化"。
5. 既有 115 个测试不回归。

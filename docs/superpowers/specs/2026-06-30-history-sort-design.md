# 历史按时间倒序显示 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-30
- **基础分支**: `main`(v0.2.1)
- **背景**: 历史"排序"原标为已完成,但实测发现只加了时间列、未真正排序——依赖隐式存储顺序,timestamp 与顺序不一致时乱序(虚假完成)

## 1. 目标

历史 Tab 按 `timestamp` 倒序显示(最新在最上),不依赖隐式存储契约。

## 2. 缺陷证据

插入顺序 a(ts=1000)→c(ts=3000)→b(ts=2000),显示却是 b→c→a(乱序)。
`_refresh_history` 直接遍历 `items` 填充,未排序;`add_history_entry` 的 LRU 插入在 timestamp 与插入顺序不一致时失效。

## 3. 方案

`_refresh_history` 填充前显式按 timestamp 倒序排序:
- 有 timestamp 的按值倒序(大→小,即新→旧)
- 无 timestamp 的(理论上不存在,防御性)排末尾

```python
items = sorted(items, key=lambda e: e.get("timestamp") or 0, reverse=True)
```

## 4. 涉及文件

- `src/hwtransmib/ui/main_window.py`(`_refresh_history` 加排序)
- `tests/ui/test_main_window_state.py`(新增/修正排序测试)

## 5. 验收标准
1. 乱序 timestamp 插入后,历史按时间倒序显示(最新在最上)。
2. 无 timestamp 的条目排末尾。
3. 既有 128 个测试不回归。

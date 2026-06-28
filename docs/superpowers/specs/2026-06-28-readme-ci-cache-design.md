# README 文档 + CI 缓存 设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-28
- **基础分支**: `main`(含中优先级优化)
- **背景**: README 空文件(真实缺口);CI 每次重装依赖慢

## 1. 目标

| 项 | 目标 |
|---|---|
| README 文档 | 填充空的 README.md,面向开发者,克隆即可照着跑 |
| CI 缓存 | uv 依赖缓存加速二次构建;升级 checkout 消除 Node 20 警告 |

## 2. #1 README 开发者文档

### 内容结构(中文,面向开发者)

1. **项目简介** —— 一句话定位 + 简短说明
2. **功能特性** —— 导入解析、OID 树浏览、节点属性(含索引构成)、模糊搜索、OID 构造(标量/表列/多列/IMPLIED)、收藏与历史、三平台打包
3. **技术栈** —— Python ≥3.11、PySide6、PySnmp 7.1、PySMI、uv
4. **快速开始(开发环境)**
   - 环境要求(uv)
   - `uv sync --extra dev`
   - `uv run hwtransmib` 启动
5. **测试** —— `uv run pytest`;说明覆盖率(内核 ≥90%);性能基准脚本
6. **项目结构** —— src/hwtransmib 四层(kernel/services/persistence/ui)简图
7. **打包发布**
   - 本地:`./build.sh`(macOS)
   - CI:打 tag `v*` 自动三平台构建并发布 Release
8. **License**(MIT,占位)

### 涉及文件
- `README.md`(从空填充)
- `LICENSE`(新建,MIT 文本)

## 3. #2 CI 缓存 + checkout 升级

### 缓存方案
`astral-sh/setup-uv@v3` 内置缓存(`enable-cache`):
- 缓存 uv 全局目录(`~/.local/share/uv`)
- key 按 `pyproject.toml` + `uv.lock` 的 hash
- 命中后 `uv sync` 秒级完成(不再重新下载 PySide6)

### checkout 升级
`actions/checkout@v4` → `@v5`(消除 Node 20 deprecation 警告)。

### 涉及文件
- `.github/workflows/build.yml`

## 4. 验收标准
1. README 含 8 个章节,克隆者按"快速开始"能跑起应用和测试。
2. CI 二次构建命中缓存,`uv sync` 步骤耗时可观察下降。
3. CI 日志无 Node 20 deprecation 警告。
4. 既有 122 个测试不回归。

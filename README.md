# HWTransMIB

跨平台的 SNMP MIB 浏览与 OID 构造工具。导入 MIB 文件,以树形结构浏览,查看节点属性,搜索节点,对选中节点交互式构造完整 OID 访问字符串。

## 功能特性

- **MIB 导入解析** —— 支持纯文本 MIB、多文件批量导入、自动跨文件依赖解析;内置宽松解析器容忍厂商 MIB 的常见语法瑕疵(尾随逗号等)
- **OID 层级树** —— 按 OID 层级组织,展开状态记忆(关闭重开自动恢复)
- **节点属性面板** —— 键值对展示(SYNTAX/ACCESS/STATUS/DESCRIPTION 等);TABLE/ROW 节点显示索引构成(列名/OID/类型/IMPLIED)
- **模糊搜索** —— 实时匹配节点名称/OID/描述,结果列表点击跳转
- **OID 构造** —— 标量(`.0`)、表列索引、多列复合索引、IMPLIED 字符串、TC 包装整数类型(防崩溃)
- **收藏与历史** —— 收藏节点、OID 构造历史(带时间戳),重启后保留
- **三平台打包** —— macOS/Windows/Linux 单文件可执行,零运行时依赖

## 技术栈

- Python ≥ 3.11
- [PySide6](https://www.qt.io/) —— Qt GUI
- [PySnmp 7.1](https://docs.lextudio.com/pysnmp/) + [PySMI](https://github.com/lextudio/pysmi) —— MIB 解析与索引编码
- [uv](https://docs.astral.sh/uv/) —— 环境与依赖管理

## 快速开始(开发环境)

### 环境要求

- [uv](https://docs.astral.sh/uv/) (安装:`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### 安装与运行

```bash
git clone https://github.com/leezii/HWTransMIB.git
cd HWTransMIB
uv sync --extra dev        # 安装依赖(含开发工具)
uv run hwtransmib          # 启动应用
```

## 测试

```bash
uv run pytest              # 全量测试
uv run pytest tests/kernel --cov=hwtransmib.kernel --cov-report=term   # 内核覆盖率(≥90%)
```

性能基准(大 MIB 搜索耗时):

```bash
uv run python tests/perf/bench_search.py
```

## 项目结构

```
src/hwtransmib/
├── kernel/         # MIB 内核(纯 Python,无 Qt 依赖)
│   ├── model.py            # MibNode / NodeType / IndexSpec 领域模型
│   ├── mib_parser.py       # 封装 PySnmp MibBuilder + PySMI 宽松编译
│   ├── tree_builder.py     # 构建 OID 树 + 节点类型推断 + 索引提取
│   ├── oid_builder.py      # OID 构造引擎(复用 PySnmp 索引编码)
│   ├── search_index.py     # 名称/OID/描述模糊匹配
│   └── standard_mibs/      # 内置标准 MIB(SNMPv2-*/IF-MIB 等)
├── services/       # 应用服务层(编排)
├── persistence/    # 持久化层(JSON 原子读写)
└── ui/             # UI 层(PySide6)
```

四层单向依赖:UI → 服务 → 内核 → 持久化。内核层可脱离 GUI 独立测试。

## 打包发布

### 本地打包(macOS)

```bash
./build.sh                  # 产出 dist/HWTransMIB.app
```

### CI 自动构建(三平台)

打 tag 触发 GitHub Actions 自动构建 macOS/Windows/Linux 三个平台的单文件可执行程序,并发布到 Releases 页:

```bash
git tag -a v0.1.x -m "版本说明"
git push origin v0.1.x
```

用户从 [Releases](https://github.com/leezii/HWTransMIB/releases) 下载对应平台的压缩包,解压双击即可运行,无需安装 Python 或任何依赖。

## License

MIT

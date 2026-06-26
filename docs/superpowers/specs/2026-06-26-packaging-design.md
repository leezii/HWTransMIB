# HWTransMIB 打包设计规格

- **状态**: 已确认,待制定实现计划
- **日期**: 2026-06-26
- **基础分支**: `main`(v0.1)
- **背景**: 需产出 macOS/Windows/Linux 三平台单文件可执行程序,零运行时依赖

## 1. 目标

| 目标 | 说明 |
|---|---|
| 三平台可执行 | macOS(.app)、Windows(.exe)、Linux(ELF),单文件分发 |
| 零运行时依赖 | 目标机器无需安装 Python 或任何依赖 |
| 本地可打 macOS | 开发者本地 PyInstaller 直接产出 macOS 包 |
| CI 自动三平台 | GitHub Actions 在打 tag 时自动构建三平台产物并发布 Release |
| 资源完整打包 | 内置标准 MIB 库 + 应用图标随包分发 |

## 2. 技术选型

| 项 | 选择 | 理由 |
|---|---|---|
| 打包器 | PyInstaller | 成熟,PySide6 兼容好,CI 模板多,速度快 |
| CI | GitHub Actions | 免费,三平台 runner,tag 触发 |
| 产物形式 | `--onefile --windowed` | 单文件无控制台,下载即用 |

**为何不用 Nuitka:** 编译成 C 理论更优,但对 PySide6 大库兼容风险高、CI 耗时十几分钟+,得不偿失。

**交叉打包限制:** PyInstaller 是原生打包器,只能在运行它的 OS 上产出对应平台产物。故 macOS 本地只能产 macOS 包,Windows/Linux 包必须经 CI。

## 3. 本地打包(macOS)

### 3.1 资源打包

应用含两类非 Python 资源,必须随包分发:
- `src/hwtransmib/kernel/standard_mibs/`(9 个标准 MIB 文本文件)
- `src/hwtransmib/ui/resources/app-icon.png`

PyInstaller 用 `--add-data` 打入,运行时通过 `importlib.resources` 定位(已实现,兼容 `_MEIPASS`)。

### 3.2 PyInstaller 命令

```bash
pyinstaller --noconfirm \
  --name hwtransmib \
  --windowed \
  --onefile \
  --add-data "src/hwtransmib/kernel/standard_mibs:hwtransmib/kernel/standard_mibs" \
  --add-data "src/hwtransmib/ui/resources:hwtransmib/ui/resources" \
  --collect-all PySide6 \
  src/hwtransmib/ui/app.py
```

- `--windowed`:macOS 生成 `.app` bundle(无终端),Windows 无控制台
- `--onefile`:单文件
- `--collect-all PySide6`:确保 Qt 插件(qml/platforms/styles)齐全
- `--add-data`:`源路径:目标路径`(macOS/Linux 用 `:`,Windows 用 `;`)

### 3.3 macOS Info.plist 与 Dock 图标

`--windowed` 生成的 `.app` 含默认 Info.plist。为使 Dock 显示自定义图标:
- 生成 `app-icon.icns`(从 PNG 转换)
- `--icon app-icon.icns` 指定
- 或用 `--osx-bundle-identifier` 设置 bundle id

### 3.4 .spec 文件

将命令固化为 `hwtransmib.spec`,支持可复现打包,处理跨平台 `--add-data` 分隔符差异。

## 4. GitHub Actions CI

### 4.1 触发

- `push tag v*`:触发三平台构建并发布 Release
- `workflow_dispatch`:手动触发(测试用)

### 4.2 三平台矩阵

```yaml
strategy:
  matrix:
    os: [macos-latest, windows-latest, ubuntu-latest]
runs-on: ${{ matrix.os }}
```

每个平台:
1. checkout 代码
2. uv 安装依赖
3. PyInstaller 打包(用平台对应的分隔符)
4. 打包产物(压缩为 zip/tar.gz)
5. 上传为 Release 资产

### 4.3 产物命名

- macOS: `hwtransmib-macos.zip`(含 `.app`)
- Windows: `hwtransmib-windows.zip`(含 `.exe`)
- Linux: `hwtransmib-linux.tar.gz`(含 ELF 可执行)

### 4.4 Linux 额外注意

PySide6 在 Linux 需系统有 X11 相关库。CI 的 ubuntu-latest 已含;终端用户需有桌面环境(GNOME/KDE 等标准发行版均自带)。

## 5. 涉及文件

| 文件 | 用途 |
|---|---|
| `hwtransmib.spec` | 新增:PyInstaller 配置(可复现打包) |
| `build.sh` / `build.py` | 新增:本地打包脚本(macOS) |
| `.github/workflows/build.yml` | 新增:三平台 CI |
| `src/hwtransmib/ui/resources/app-icon.icns` | 新增:macOS 图标(从 PNG 转) |
| `pyproject.toml` | 修改:dev 依赖加 pyinstaller |

## 6. 测试与验收

| 项 | 验证方式 |
|---|---|
| macOS 本地打包 | `./build.sh` 产出 `dist/hwtransmib.app`,双击启动正常 |
| 资源完整 | 启动后导入私有 MIB,标准依赖(SNMPv2-SMI)能找到(证明内置 MIB 打包成功) |
| 图标显示 | macOS Dock / Windows 任务栏显示树主题图标 |
| CI 三平台 | 打 tag v0.1.1,Actions 产出三个产物,Release 含三个资产 |
| Windows 产物 | 下载 windows zip,在 Windows 机器解压双击运行 |
| Linux 产物 | 下载 linux tar.gz,在 Linux 桌面环境运行 |

## 7. 已知限制

- **交叉打包不可行**:Windows/Linux 包必须经 CI,本地 macOS 无法直接产出
- **Linux 运行环境**:需有桌面环境(X11/Wayland + Qt 依赖),无头服务器无法运行 GUI
- **产物体积**:单文件约 80-150MB(PySide6 含完整 Qt),首次启动需解压到临时目录(略慢)
- **代码签名**:v0.1 不做代码签名(macOS Gatekeeper 需右键打开,Windows SmartScreen 警告);后续版本可加

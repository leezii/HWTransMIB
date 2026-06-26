# HWTransMIB 打包实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 PyInstaller 打包 HWTransMIB 为三平台(macOS/Windows/Linux)单文件可执行程序,本地可产 macOS 包,GitHub Actions 自动产三平台包并发布 Release。

**Architecture:** 两层打包——本地 PyInstaller `--onefile --windowed` 产 macOS 包;GitHub Actions 三平台矩阵在 tag 触发时产三平台产物。资源(标准 MIB + 图标)用 `importlib.resources` 加载,兼容 PyInstaller `_MEIPASS`。

**Tech Stack:** PyInstaller、GitHub Actions、uv、PySide6。

**参考规格:** `docs/superpowers/specs/2026-06-26-packaging-design.md`

---

## 文件结构

```
hwtransmib.spec                    # 新增: PyInstaller 配置(可复现打包)
build.sh                           # 新增: 本地打包脚本
src/hwtransmib/ui/app.py           # 修改: _standard_mibs_dir 改用 importlib.resources
src/hwtransmib/ui/resources/
    app-icon.png                   # 已有
    app-icon.icns                  # 新增: macOS 图标(从 PNG 转)
.github/workflows/build.yml        # 新增: 三平台 CI
pyproject.toml                     # 修改: dev 依赖加 pyinstaller
```

---

## Task 1: 修复资源加载兼容 PyInstaller

`_standard_mibs_dir()` 当前用 `__file__` 路径,PyInstaller onefile 模式下失效。改为 `importlib.resources`(与 `_app_icon_path` 一致)。

**Files:**
- Modify: `src/hwtransmib/ui/app.py:18-23`
- Test: `tests/ui/test_app_resources.py`

- [ ] **Step 1: 编写失败测试**

创建 `tests/ui/test_app_resources.py`:

```python
"""应用资源加载测试(兼容 PyInstaller)。"""
from hwtransmib.ui.app import _app_icon_path, _standard_mibs_dir


def test_standard_mibs_dir_found():
    """标准 MIB 目录能被定位(用 importlib.resources,非 __file__)。"""
    path = _standard_mibs_dir()
    assert path is not None
    from pathlib import Path
    assert Path(path).is_dir()


def test_standard_mibs_dir_contains_files():
    """标准 MIB 目录含 MIB 文件。"""
    from pathlib import Path
    path = Path(_standard_mibs_dir())
    files = list(path.iterdir())
    assert len(files) > 0
    # 至少含 SNMPv2-SMI
    assert any("SNMPv2-SMI" in f.name for f in files)


def test_app_icon_path_found():
    """应用图标能被定位。"""
    path = _app_icon_path()
    assert path is not None
    assert "app-icon.png" in path
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/ui/test_app_resources.py -v`
Expected: `test_standard_mibs_dir_*` 通过(当前实现碰巧能用源码路径),但实现方式依赖 `__file__`,PyInstaller 下会失败。本任务改实现使其健壮。

> 注:测试可能因当前 `__file__` 实现在源码下通过,但目标是改用 importlib.resources 以兼容打包。先确认测试在改实现后仍通过。

- [ ] **Step 3: 修改 _standard_mibs_dir 用 importlib.resources**

将 `src/hwtransmib/ui/app.py` 的 `_standard_mibs_dir` 替换为:

```python
def _standard_mibs_dir() -> str | None:
    """返回随包分发的标准 MIB 目录(兼容源码与 PyInstaller 打包)。

    用 importlib.resources 定位,而非 __file__——后者在 PyInstaller
    onefile 模式下指向临时解压目录的错误位置。
    """
    try:
        import importlib.resources
        res = importlib.resources.files("hwtransmib.kernel") / "standard_mibs"
        with importlib.resources.as_file(res) as p:
            return str(p) if p.is_dir() else None
    except Exception:
        return None
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/ui/test_app_resources.py -v`
Expected: 3 passed。

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `uv run pytest`
Expected: 全部 passed(原 108 + 3 = 111)。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "fix(ui): load standard MIBs via importlib.resources for PyInstaller compatibility"
```

---

## Task 2: 生成 macOS 图标 + PyInstaller 依赖

**Files:**
- Create: `src/hwtransmib/ui/resources/app-icon.icns`
- Modify: `pyproject.toml`

- [ ] **Step 1: 添加 pyinstaller 为 dev 依赖**

Run: `uv add --dev pyinstaller`
Expected: pyinstaller 安装成功。

- [ ] **Step 2: 生成 macOS .icns 图标**

用 Pillow + iconutil(macOS)或直接生成多尺寸 PNG 集合。先确认 iconutil 可用:

```bash
which iconutil && echo "iconutil available" || echo "需要替代方案"
```

若 iconutil 可用(macOS):

```bash
# 生成多尺寸 iconset
ICONSET="src/hwtransmib/ui/resources/app-icon.iconset"
mkdir -p "$ICONSET"
SRC="src/hwtransmib/ui/resources/app-icon.png"
uv run python -c "
from PIL import Image
img = Image.open('$SRC')
sizes = [16,32,64,128,256,512]
for s in sizes:
    img.resize((s,s)).save('$ICONSET/icon_{0}x{0}.png'.format(s))
    img.resize((s*2,s*2)).save('$ICONSET/icon_{0}x{0}@2x.png'.format(s))
"
iconutil -c icns "$ICONSET" -o src/hwtransmib/ui/resources/app-icon.icns
rm -rf "$ICONSET"
ls -la src/hwtransmib/ui/resources/app-icon.icns
```

Expected: 生成 `app-icon.icns`(约几十 KB)。

- [ ] **Step 3: 确认 icns 加入打包配置**

`pyproject.toml` 的 `force-include` 已含 `ui/resources`,icns 在该目录内会自动包含。无需额外配置。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "build: add macOS .icns icon and pyinstaller dev dependency"
```

---

## Task 3: PyInstaller .spec 配置 + 本地打包脚本

**Files:**
- Create: `hwtransmib.spec`
- Create: `build.sh`

- [ ] **Step 1: 创建 hwtransmib.spec**

创建 `hwtransmib.spec`(PyInstaller 配置,处理跨平台分隔符):

```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。可复现,跨平台。

本地(macOS): pyinstaller hwtransmib.spec
CI: 各平台用本 spec(分隔符自动适配)。
"""
import sys
from pathlib import Path

block_cipher = None

# 跨平台 --add-data 分隔符: macOS/Linux 用 ':', Windows 用 ';'
SEP = ";" if sys.platform == "win32" else ":"

a = Analysis(
    ["src/hwtransmib/ui/app.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/hwtransmib/kernel/standard_mibs", "hwtransmib/kernel/standard_mibs"),
        ("src/hwtransmib/ui/resources", "hwtransmib/ui/resources"),
    ],
    hiddenimports=["PySide6"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# macOS 用 .app bundle(windowed),其他平台单文件
if sys.platform == "darwin":
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="hwtransmib",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        console=False,
        icon="src/hwtransmib/ui/resources/app-icon.icns",
    )
    app = BUNDLE(
        exe,
        name="HWTransMIB.app",
        icon="src/hwtransmib/ui/resources/app-icon.icns",
        bundle_identifier="com.hwtransmib.app",
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="hwtransmib",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        runtime_tmpdir=None,
        console=False,
        icon="src/hwtransmib/ui/resources/app-icon.png",
    )
```

- [ ] **Step 2: 创建 build.sh**

创建 `build.sh`(本地 macOS 打包脚本):

```bash
#!/usr/bin/env bash
# 本地打包脚本(macOS)。
# 产出 dist/HWTransMIB.app。
set -e

echo "=== 清理旧产物 ==="
rm -rf build dist

echo "=== PyInstaller 打包 ==="
uv run pyinstaller --noconfirm hwtransmib.spec

echo "=== 打包完成 ==="
ls -la dist/
echo "产物: dist/HWTransMIB.app"
```

```bash
chmod +x build.sh
```

- [ ] **Step 3: 本地打包验证(macOS)**

Run: `./build.sh`
Expected: `dist/HWTransMIB.app` 生成,无报错。

- [ ] **Step 4: 启动验证**

Run: `open dist/HWTransMIB.app`
Expected: 应用窗口弹出,无崩溃。

- [ ] **Step 5: 资源完整性验证**

启动后,手动导入一个私有 MIB(依赖 SNMPv2-SMI),确认内置标准 MIB 能被找到(不报依赖缺失)。

- [ ] **Step 6: 图标验证**

确认 Dock 显示树主题图标(而非默认 Python 图标)。

- [ ] **Step 7: Commit**

```bash
git add hwtransmib.spec build.sh
git commit -m "build: add PyInstaller spec and local build script"
```

---

## Task 4: GitHub Actions 三平台 CI

**Files:**
- Create: `.github/workflows/build.yml`

- [ ] **Step 1: 创建 build.yml**

创建 `.github/workflows/build.yml`:

```yaml
name: Build

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: macos-latest
            artifact: hwtransmib-macos.zip
            archive_cmd: cd dist && zip -r ../hwtransmib-macos.zip HWTransMIB.app && cd ..
          - os: windows-latest
            artifact: hwtransmib-windows.zip
            archive_cmd: cd dist && 7z a ../hwtransmib-windows.zip hwtransmib.exe && cd ..
          - os: ubuntu-latest
            artifact: hwtransmib-linux.tar.gz
            archive_cmd: cd dist && tar czf ../hwtransmib-linux.tar.gz hwtransmib && cd ..

    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Build with PyInstaller
        run: uv run pyinstaller --noconfirm hwtransmib.spec

      - name: Package artifact
        run: ${{ matrix.archive_cmd }}

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: ${{ matrix.artifact }}

      - name: Release
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          files: ${{ matrix.artifact }}
```

- [ ] **Step 2: 验证 workflow 语法**

Run: `cat .github/workflows/build.yml | head -5`
确认 YAML 结构正确。

- [ ] **Step 3: 添加 Linux 系统依赖注释**

ubuntu runner 的 PySide6 需要的 X11/Qt 库在 `ubuntu-latest` 默认已含。若 CI 报库缺失,在 build 步骤前加:

```yaml
      - name: Install Linux Qt dependencies
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y libxkbcommon-x11-0 libegl1 libgl1
```

(先不加,观察首次 CI 结果再决定。)

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "ci: add tri-platform build workflow (GitHub Actions)"
```

---

## Task 5: 推送远程 + 首次 CI 验证

- [ ] **Step 1: 创建 GitHub 仓库并推送**

```bash
gh repo create hwtransmib --private --source=. --push
```
(若已有远程,跳过。)

- [ ] **Step 2: 推送当前分支**

```bash
git push -u origin main
```

- [ ] **Step 3: 手动触发 workflow_dispatch 测试**

在 GitHub 仓库 Actions 页,手动触发 `Build` workflow,观察三平台是否都构建成功。

或用 CLI:

```bash
gh workflow run build.yml
gh run watch
```

- [ ] **Step 4: 检查产物下载**

三平台产物作为 artifact 上传。下载验证:

```bash
gh run download <run-id>
ls -la
```

- [ ] **Step 5: 打 tag 触发 Release(验证完整流程)**

```bash
git tag -a v0.1.1 -m "v0.1.1: add packaging"
git push origin v0.1.1
```

观察:tag 推送 → CI 触发 → 三平台构建 → Release 页出现三个资产。

---

## 自审清单(对照规格)

- [x] 三平台可执行 → Task 4 CI 矩阵
- [x] 零运行时依赖 → PyInstaller --onefile
- [x] 本地可打 macOS → Task 3 build.sh
- [x] CI 自动三平台 → Task 4 + Task 5
- [x] 资源完整打包 → Task 1(importlib.resources)+ spec datas
- [x] macOS Info.plist/Dock 图标 → Task 2 icns + spec BUNDLE
- [x] Windows 无控制台 → spec console=False
- [x] 产物命名约定 → Task 4 matrix artifact
- [x] 验收 6 项 → Task 3 Step 3-6 + Task 5 Step 3-5
- [x] 已知限制(交叉打包不可行等)→ 规格 7 节已记录

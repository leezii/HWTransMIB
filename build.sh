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

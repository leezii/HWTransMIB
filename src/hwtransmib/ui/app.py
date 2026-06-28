"""应用入口。

启动时将内置标准 MIB 库目录加入 PySnmp 搜索路径,
让用户导入私有 MIB 时自动补齐标准依赖(如 SNMPv2-SMI)。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.ui.main_window import MainWindow


def _resource_dir(subpath: str) -> str | None:
    """返回随包分发的资源目录(兼容源码与 PyInstaller 打包)。

    PyInstaller onefile 模式:资源解压到 sys._MEIPASS,用它在临时目录定位。
    源码运行:回退到 importlib.resources 定位安装路径。
    """
    import sys
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / subpath
        if candidate.is_dir():
            return str(candidate)
    try:
        import importlib.resources
        parts = subpath.split("/")
        pkg = ".".join(parts[:-1])
        name = parts[-1]
        res = importlib.resources.files(pkg) / name
        with importlib.resources.as_file(res) as p:
            return str(p) if p.is_dir() else None
    except Exception:
        return None
    return None


def _standard_mibs_dir() -> str | None:
    """返回随包分发的标准 MIB 目录。"""
    return _resource_dir("hwtransmib/kernel/standard_mibs")


def _app_icon_path() -> str | None:
    """返回随包分发的应用图标。"""
    path = _resource_dir("hwtransmib/ui/resources")
    if path is None:
        return None
    candidate = Path(path) / "app-icon.png"
    return str(candidate) if candidate.exists() else None


def main() -> int:
    app = QApplication(sys.argv)

    # 应用图标(窗口标题栏 + 任务栏)
    from PySide6.QtGui import QIcon
    icon_path = _app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    sources = []
    std_dir = _standard_mibs_dir()
    if std_dir:
        sources.append(std_dir)

    window = MainWindow(
        import_service=ImportService(extra_sources=sources),
        user_data=UserData(),
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

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


def _standard_mibs_dir() -> str | None:
    """返回随包分发的标准 MIB 目录(若存在)。"""
    here = Path(__file__).resolve().parent
    # kernel 包下的 standard_mibs 目录
    candidate = here.parent / "kernel" / "standard_mibs"
    return str(candidate) if candidate.is_dir() else None


def main() -> int:
    app = QApplication(sys.argv)
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

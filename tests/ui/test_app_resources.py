"""应用资源加载测试(兼容 PyInstaller)。"""
from pathlib import Path

from hwtransmib.ui.app import _app_icon_path, _standard_mibs_dir


def test_standard_mibs_dir_found():
    """标准 MIB 目录能被定位(用 importlib.resources,非 __file__)。"""
    path = _standard_mibs_dir()
    assert path is not None
    assert Path(path).is_dir()


def test_standard_mibs_dir_contains_files():
    """标准 MIB 目录含 MIB 文件。"""
    path = Path(_standard_mibs_dir())
    files = list(path.iterdir())
    assert len(files) > 0
    assert any("SNMPv2-SMI" in f.name for f in files)


def test_app_icon_path_found():
    """应用图标能被定位。"""
    path = _app_icon_path()
    assert path is not None
    assert "app-icon.png" in path

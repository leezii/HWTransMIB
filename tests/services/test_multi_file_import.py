"""多文件 + 跨文件依赖导入测试。

模拟华为 OPTIX MIB 场景:多个私有 MIB 互相依赖(如 MY-CHILD-MIB
依赖 MY-BASE-MIB),且都是纯文本文件。验证 ImportService 能正确编译
并按依赖顺序加载。
"""
from pathlib import Path

import pytest

from hwtransmib.services.import_service import ImportService


@pytest.fixture
def dep_dir():
    return Path(__file__).parent.parent / "fixtures" / "mibs_dep"


def test_multi_file_import_with_dependency(dep_dir):
    """两个互相依赖的纯文本 MIB 同时导入。"""
    svc = ImportService()
    files = [str(dep_dir / "MY-BASE-MIB"), str(dep_dir / "MY-CHILD-MIB")]
    report = svc.import_files(files)
    assert "MY-BASE-MIB" in report.loaded_modules
    assert "MY-CHILD-MIB" in report.loaded_modules
    assert not report.errors


def test_child_mib_node_resolves(dep_dir):
    """子 MIB 节点能解析(依赖的父 MIB 已加载)。"""
    svc = ImportService()
    svc.import_files([
        str(dep_dir / "MY-BASE-MIB"),
        str(dep_dir / "MY-CHILD-MIB"),
    ])
    root = svc.get_root()
    # myChildMIB ::= { myBaseMIB 1 } = ...88888.1
    node = root.find("1.3.6.1.4.1.88888.1")
    assert node is not None
    assert node.name == "myChildMIB"


def test_import_order_independent(dep_dir):
    """导入顺序不影响(先 child 后 base 也能成功,依赖自动补齐)。"""
    svc = ImportService()
    svc.import_files([
        str(dep_dir / "MY-CHILD-MIB"),  # 先导入依赖方
        str(dep_dir / "MY-BASE-MIB"),
    ])
    report = svc.import_files.__self__._import.import_files if False else None
    # 重新验证
    svc2 = ImportService()
    r = svc2.import_files([
        str(dep_dir / "MY-CHILD-MIB"),
        str(dep_dir / "MY-BASE-MIB"),
    ])
    assert "MY-BASE-MIB" in r.loaded_modules
    assert "MY-CHILD-MIB" in r.loaded_modules

"""共享 pytest fixture。"""
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_mibs_dir() -> Path:
    """测试用真实 MIB 文件目录。"""
    return Path(__file__).parent / "fixtures" / "mibs"


@pytest.fixture(scope="session")
def if_mib_path(fixtures_mibs_dir: Path) -> Path:
    """IF-MIB 文件路径。"""
    return fixtures_mibs_dir / "IF-MIB"

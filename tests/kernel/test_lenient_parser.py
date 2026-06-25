"""宽松解析器回归测试: 处理厂商 MIB 的尾随逗号等语法瑕疵。

复现并锁定缺陷: 华为/中兴等厂商 MIB 的 INTEGER 枚举/SEQUENCE 末尾常带
尾随逗号(name(value), }),严格 SMIv2 解析器拒绝。宽松 parserFactory
通过 commaAtTheEndOfSequence 等选项容忍这类真实世界语法。
"""
from pathlib import Path

import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def lenient_dir():
    return Path(__file__).parent.parent / "fixtures" / "mibs_lenient"


@pytest.fixture
def parser(lenient_dir):
    return MibParser(extra_sources=[str(lenient_dir)])


def test_trailing_comma_mib_imports(parser):
    """含尾随逗号的 MIB 能被编译加载(严格解析器会拒绝)。"""
    result = parser.parse(["TRAILING-COMMA-MIB"])
    assert "TRAILING-COMMA-MIB" in result.loaded_modules
    assert not result.errors


def test_trailing_comma_mib_node_queryable(parser):
    """尾随逗号 MIB 的节点可查询。"""
    parser.parse(["TRAILING-COMMA-MIB"])
    oid = parser.get_oid_by_name("trailingCommaMIB")
    assert oid == "1.3.6.1.4.1.66666"


def test_trailing_comma_enum_object_type(parser):
    """尾随逗号枚举的 OBJECT-TYPE 节点能正确出现在树中。"""
    parser.parse(["TRAILING-COMMA-MIB"])
    root = MibTreeBuilder(parser).build()
    node = root.find("1.3.6.1.4.1.66666.1")  # portType
    assert node is not None
    assert node.name == "portType"

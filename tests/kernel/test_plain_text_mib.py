"""纯文本 MIB 导入回归测试。

复现并锁定缺陷: PySnmp 的 DirMibSource 不会自动编译纯文本 MIB 源文件,
必须用 PySMI 的 MibCompiler 显式编译。本测试验证私有纯文本 MIB 能被导入。
"""
import pytest

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@pytest.fixture
def parser(fixtures_mibs_dir):
    return MibParser(extra_sources=[str(fixtures_mibs_dir)])


def test_compile_and_load_plain_text_mib(parser):
    """纯文本私有 MIB(TEST-PRIVATE-MIB)能被编译并加载。"""
    result = parser.parse(["TEST-PRIVATE-MIB"])
    assert "TEST-PRIVATE-MIB" in result.loaded_modules
    assert not result.errors


def test_plain_text_mib_node_queryable(parser):
    """编译后的私有 MIB 节点可查询。"""
    parser.parse(["TEST-PRIVATE-MIB"])
    # testPrivateMIB ::= { enterprises 99999 } = 1.3.6.1.4.1.99999
    oid = parser.get_oid_by_name("testPrivateMIB")
    assert oid == "1.3.6.1.4.1.99999"


def test_plain_text_mib_in_tree(parser):
    """编译后的私有 MIB 节点出现在树中。"""
    parser.parse(["TEST-PRIVATE-MIB"])
    root = MibTreeBuilder(parser).build()
    node = root.find("1.3.6.1.4.1.99999")
    assert node is not None
    assert node.name == "testPrivateMIB"


def test_plain_text_mib_object_type(parser):
    """私有 MIB 的 OBJECT-TYPE 节点类型推断正确。"""
    parser.parse(["TEST-PRIVATE-MIB"])
    root = MibTreeBuilder(parser).build()
    node = root.find("1.3.6.1.4.1.99999.1")  # testObject
    assert node is not None
    assert node.is_constructible  # 标量,可构造

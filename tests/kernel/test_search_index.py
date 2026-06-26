"""SearchIndex 测试:名称/OID/描述模糊匹配。"""
from hwtransmib.kernel.model import MibNode, NodeType
from hwtransmib.kernel.search_index import SearchIndex


def _make_tree() -> MibNode:
    root = MibNode("1.3", "org", NodeType.SUBTREE)
    a = MibNode("1.3.6.1.2.1.2.2.1.2", "ifDescr", NodeType.COLUMN,
                description="A textual string about the interface", parent=root)
    b = MibNode("1.3.6.1.2.1.1.1", "sysDescr", NodeType.SCALAR, parent=root)
    root.children = [a, b]
    return root


def test_search_by_name_substring():
    idx = SearchIndex(_make_tree())
    results = idx.search("descr")
    names = [r.name for r in results]
    assert "ifDescr" in names
    assert "sysDescr" in names


def test_search_by_oid_substring():
    idx = SearchIndex(_make_tree())
    results = idx.search("2.2.1.2")
    assert any(r.name == "ifDescr" for r in results)


def test_search_case_insensitive():
    idx = SearchIndex(_make_tree())
    results = idx.search("IFDESCR")
    assert any(r.name == "ifDescr" for r in results)


def test_search_by_description_keyword():
    idx = SearchIndex(_make_tree())
    results = idx.search("interface")
    assert any(r.name == "ifDescr" for r in results)


def test_search_no_match():
    idx = SearchIndex(_make_tree())
    assert idx.search("zzzznotfound") == []


def test_search_empty_query():
    idx = SearchIndex(_make_tree())
    assert idx.search("   ") == []


def test_search_exact_oid_prioritized():
    idx = SearchIndex(_make_tree())
    results = idx.search("1.3.6.1.2.1.2.2.1.2")
    assert results and results[0].name == "ifDescr"

"""SearchService 测试:封装 SearchIndex。"""
import pytest

from hwtransmib.services.import_service import ImportService
from hwtransmib.services.search_service import SearchService


@pytest.fixture
def service(fixtures_mibs_dir):
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
    imp.import_files([str(fixtures_mibs_dir / "IF-MIB")])
    return SearchService(root=imp.get_root())


def test_search_returns_nodes(service):
    results = service.search("ifDescr")
    assert any(r.name == "ifDescr" for r in results)


def test_search_empty_query_returns_empty(service):
    assert service.search("   ") == []


def test_search_oid(service):
    results = service.search("2.2.1.2")
    assert any(r.name == "ifDescr" for r in results)


def test_rebuild(service, fixtures_mibs_dir):
    # 重新导入后重建索引
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
    imp.import_files([str(fixtures_mibs_dir / "SNMPv2-MIB")])
    service.rebuild(imp.get_root())
    results = service.search("sysDescr")
    assert any(r.name == "sysDescr" for r in results)

"""ImportService 测试:从文件路径解析 MIB 并构建树。"""
import pytest

from hwtransmib.services.import_service import ImportReport, ImportService


@pytest.fixture
def service(fixtures_mibs_dir):
    return ImportService(extra_sources=[str(fixtures_mibs_dir)])


def test_import_returns_report(service, if_mib_path):
    report = service.import_files([str(if_mib_path)])
    assert isinstance(report, ImportReport)
    assert "IF-MIB" in report.loaded_modules
    assert report.node_count > 0


def test_get_root_after_import(service, if_mib_path):
    service.import_files([str(if_mib_path)])
    root = service.get_root()
    assert root.oid == "1"
    assert root.name == "iso"


def test_get_root_before_import_raises(service):
    with pytest.raises(RuntimeError):
        service.get_root()


def test_import_reports_missing_file(service):
    report = service.import_files(["/nonexistent/Fake-MIB"])
    assert report.errors
    assert "IF-MIB" not in report.loaded_modules


def test_get_parser_after_import(service, if_mib_path):
    service.import_files([str(if_mib_path)])
    assert service.get_parser().is_loaded("IF-MIB")


def test_import_multiple_files(service, fixtures_mibs_dir):
    report = service.import_files([
        str(fixtures_mibs_dir / "IF-MIB"),
        str(fixtures_mibs_dir / "SNMPv2-MIB"),
    ])
    assert "IF-MIB" in report.loaded_modules
    assert "SNMPv2-MIB" in report.loaded_modules

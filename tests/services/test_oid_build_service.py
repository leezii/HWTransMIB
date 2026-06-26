"""OidBuildService 测试:构造 + 记录历史。"""
import pytest

from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.services.oid_build_service import OidBuildService


@pytest.fixture
def setup(fixtures_mibs_dir, tmp_path):
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
    imp.import_files([str(fixtures_mibs_dir / "IF-MIB")])
    root = imp.get_root()
    parser = imp.get_parser()
    ud = UserData(base_dir=tmp_path)
    return OidBuildService(parser=parser, root=root, user_data=ud), root, ud


def test_build_records_history(setup):
    svc, root, ud = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")  # ifDescr
    oid = svc.build_and_record(node, {"ifIndex": "5"})
    assert oid == "1.3.6.1.2.1.2.2.1.2.5"
    items = ud.history()["items"]
    assert items[0]["oid"] == oid
    assert items[0]["name"] == "ifDescr"


def test_build_scalar(setup):
    svc, root, ud = setup
    node = root.find("1.3.6.1.2.1.2.1")  # ifNumber 标量
    oid = svc.build_and_record(node, {})
    assert oid.endswith(".0")
    assert ud.history()["items"][0]["oid"] == oid


def test_validate_returns_errors(setup):
    svc, root, _ = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")
    errors = svc.validate(node, {"ifIndex": "abc"})
    assert errors


def test_validate_ok(setup):
    svc, root, _ = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")
    assert svc.validate(node, {"ifIndex": "5"}) == []

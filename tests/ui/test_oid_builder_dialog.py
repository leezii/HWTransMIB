"""OidBuilderDialog 测试:标量显示 .0,表列实时预览。"""
import pytest

from hwtransmib.persistence.user_data import UserData
from hwtransmib.services.import_service import ImportService
from hwtransmib.services.oid_build_service import OidBuildService
from hwtransmib.ui.oid_builder_dialog import OidBuilderDialog


@pytest.fixture
def setup(fixtures_mibs_dir, tmp_path):
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir)])
    imp.import_files([str(fixtures_mibs_dir / "IF-MIB")])
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    return svc, imp.get_root()


def test_scalar_dialog_shows_zero(qtbot, setup):
    svc, root = setup
    node = root.find("1.3.6.1.2.1.2.1")  # ifNumber 标量
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    assert ".0" in dlg.result_text()


def test_column_dialog_updates_on_input(qtbot, setup):
    svc, root = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")  # ifDescr COLUMN
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    dlg.set_index_value("ifIndex", "7")
    assert dlg.result_text().endswith(".7")


def test_column_invalid_input_shows_error(qtbot, setup):
    svc, root = setup
    node = root.find("1.3.6.1.2.1.2.2.1.2")
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    dlg.set_index_value("ifIndex", "abc")
    # 应显示错误提示而非有效 OID
    assert "需要整数" in dlg.result_text() or dlg.result_text().startswith("⚠")

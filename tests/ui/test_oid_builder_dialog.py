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


@pytest.fixture
def ip_setup(fixtures_mibs_dir, tmp_path):
    from pathlib import Path
    from hwtransmib.persistence.user_data import UserData
    from hwtransmib.services.import_service import ImportService
    from hwtransmib.services.oid_build_service import OidBuildService
    # IP-MIB 仅存在于 standard_mibs 目录,指向其实际位置加载。
    ip_mib = Path("src/hwtransmib/kernel/standard_mibs/IP-MIB")
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir),
                                      "src/hwtransmib/kernel/standard_mibs"])
    imp.import_files([str(ip_mib)])
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    return svc, imp.get_root()


def test_enum_column_has_completer(qtbot, ip_setup):
    """带枚举的索引列(InetVersion)应挂 QCompleter,候选项含 'ipv4 (1)'。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")  # ipIfStatsInReceives COLUMN
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    edit = dlg._inputs["ipIfStatsIPVersion"]
    assert edit.completer() is not None
    model = edit.completer().model()
    labels = [model.data(model.index(r, 0)) for r in range(model.rowCount())]
    assert "ipv4 (1)" in labels


def test_non_enum_column_has_no_completer(qtbot, ip_setup):
    """无枚举的索引列(InterfaceIndex)不挂补全器。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipIfStatsIfIndex"].completer() is None


def test_normalized_label_preview(qtbot, ip_setup):
    """选下拉 'ipv4 (1)' + 数字 5 → 规范化为枚举名,预览以 .1.5 结尾。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    dlg.set_index_value("ipIfStatsIPVersion", "ipv4 (1)")
    dlg.set_index_value("ipIfStatsIfIndex", "5")
    assert dlg.result_text().endswith(".1.5")


def test_numeric_input_preview(qtbot, ip_setup):
    """枚举列纯数字输入同样可用(数字路径)。"""
    svc, root = ip_setup
    node = root.find("1.3.6.1.2.1.4.31.3.1.3")
    dlg = OidBuilderDialog(node, svc)
    qtbot.addWidget(dlg)
    dlg.set_index_value("ipIfStatsIPVersion", "1")
    dlg.set_index_value("ipIfStatsIfIndex", "5")
    assert dlg.result_text().endswith(".1.5")

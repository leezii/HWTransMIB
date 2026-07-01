"""OidBuilderDialog 测试:标量显示 .0,表列实时预览。"""
import json

import pytest

from hwtransmib.kernel.string_templates import StringTemplateStore
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


@pytest.fixture
def ip_setup_with_templates(fixtures_mibs_dir, tmp_path):
    """IP-MIB + 一个含 IpAddress 列模板的 StringTemplateStore。

    ipNetToMediaNetAddress(OID 1.3.6.1.2.1.4.22.1.3,IpAddress 类型)是字符串类
    索引列;ipNetToMediaIfIndex(Integer32)是整数列。模板只对前者生效。
    """
    from pathlib import Path
    ip_mib = Path("src/hwtransmib/kernel/standard_mibs/IP-MIB")
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir),
                                      "src/hwtransmib/kernel/standard_mibs"])
    imp.import_files([str(ip_mib)])
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    # 预置模板:IpAddress 列(字符串类)有模板,整数列无
    tpl_file = tmp_path / "templates.json"
    tpl_file.write_text(json.dumps({"templates": [
        {"oid": "1.3.6.1.2.1.4.22.1.3", "template": "192.168.1.100"},
    ]}, ensure_ascii=False), encoding="utf-8")
    store = StringTemplateStore(tpl_file)
    store.reload()
    return svc, imp.get_root(), store


def test_string_column_prefilled_from_template(qtbot, ip_setup_with_templates):
    """字符串类索引列(IpAddress)命中模板 → 预填到输入框。"""
    svc, root, store = ip_setup_with_templates
    node = root.find("1.3.6.1.2.1.4.22.1.2")  # ipNetToMediaPhysAddress COLUMN
    dlg = OidBuilderDialog(node, svc, templates=store)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipNetToMediaNetAddress"].text() == "192.168.1.100"


def test_integer_column_not_prefilled(qtbot, ip_setup_with_templates):
    """整数列(Integer32)即使无模板也不预填(本就不查模板),保持空。"""
    svc, root, store = ip_setup_with_templates
    node = root.find("1.3.6.1.2.1.4.22.1.2")
    dlg = OidBuilderDialog(node, svc, templates=store)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipNetToMediaIfIndex"].text() == ""


def test_string_column_empty_when_no_template(qtbot, fixtures_mibs_dir, tmp_path):
    """字符串类列未命中模板 → 留空(与现状一致)。"""
    from pathlib import Path
    ip_mib = Path("src/hwtransmib/kernel/standard_mibs/IP-MIB")
    imp = ImportService(extra_sources=[str(fixtures_mibs_dir),
                                      "src/hwtransmib/kernel/standard_mibs"])
    imp.import_files([str(ip_mib)])
    svc = OidBuildService(parser=imp.get_parser(), root=imp.get_root(),
                          user_data=UserData(base_dir=tmp_path))
    # 空模板表(不 reload,内存表为空,所有 lookup 返回 None)
    store = StringTemplateStore(tmp_path / "templates.json")
    root = imp.get_root()
    node = root.find("1.3.6.1.2.1.4.22.1.2")
    dlg = OidBuilderDialog(node, svc, templates=store)
    qtbot.addWidget(dlg)
    assert dlg._inputs["ipNetToMediaNetAddress"].text() == ""

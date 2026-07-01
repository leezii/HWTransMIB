"""UserData 测试:config/imports/favorites/history 四存储。"""
from hwtransmib.persistence.user_data import UserData


def test_defaults(tmp_path):
    ud = UserData(base_dir=tmp_path)
    cfg = ud.config()
    assert "detail_visible" in cfg
    assert ud.imports() == {"files": []}
    assert ud.favorites() == {"items": []}
    assert ud.history() == {"items": []}


def test_persist_imports(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.set_imports(["/a/IF-MIB", "/b/IP-MIB"])
    ud2 = UserData(base_dir=tmp_path)
    assert ud2.imports() == {"files": ["/a/IF-MIB", "/b/IP-MIB"]}


def test_history_lru_eviction(tmp_path):
    ud = UserData(base_dir=tmp_path, history_limit=3)
    ud.add_history_entry({"oid": "1.1"})
    ud.add_history_entry({"oid": "1.2"})
    ud.add_history_entry({"oid": "1.3"})
    ud.add_history_entry({"oid": "1.4"})  # 应淘汰 1.1
    items = ud.history()["items"]
    assert [e["oid"] for e in items] == ["1.4", "1.3", "1.2"]


def test_history_dedup(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.add_history_entry({"oid": "1.1"})
    ud.add_history_entry({"oid": "1.2"})
    ud.add_history_entry({"oid": "1.1"})  # 重复,提到最前
    items = ud.history()["items"]
    assert items[0]["oid"] == "1.1"
    assert len(items) == 2


def test_add_favorite(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.add_favorite({"oid": "1.3.6.1.2.1.1.1", "name": "sysDescr"})
    assert len(ud.favorites()["items"]) == 1


def test_remove_favorite(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.add_favorite({"oid": "1.1", "name": "a"})
    ud.remove_favorite("1.1")
    assert ud.favorites()["items"] == []


def test_favorite_dedup(tmp_path):
    ud = UserData(base_dir=tmp_path)
    ud.add_favorite({"oid": "1.1", "name": "a"})
    ud.add_favorite({"oid": "1.1", "name": "a-updated"})  # 同 oid 去重
    items = ud.favorites()["items"]
    assert len(items) == 1
    assert items[0]["name"] == "a-updated"


def test_config_defaults_include_new_fields(tmp_path):
    ud = UserData(base_dir=tmp_path)
    cfg = ud.config()
    assert cfg["expanded_oids"] == []
    assert cfg["tree_column_widths"] is None


def test_persist_expanded_oids(tmp_path):
    ud = UserData(base_dir=tmp_path)
    cfg = ud.config()
    cfg["expanded_oids"] = ["1.3.6.1.4.1.2011.2.25", "1.3.6.1.2.1"]
    ud.set_config(cfg)
    ud2 = UserData(base_dir=tmp_path)
    assert ud2.config()["expanded_oids"] == ["1.3.6.1.4.1.2011.2.25", "1.3.6.1.2.1"]


def test_persist_tree_column_widths(tmp_path):
    ud = UserData(base_dir=tmp_path)
    cfg = ud.config()
    cfg["tree_column_widths"] = [533, 266]
    ud.set_config(cfg)
    ud2 = UserData(base_dir=tmp_path)
    assert ud2.config()["tree_column_widths"] == [533, 266]


def test_config_defaults_include_detail_panel_fields(tmp_path):
    ud = UserData(base_dir=tmp_path)
    cfg = ud.config()
    assert cfg["detail_split_sizes"] is None
    assert cfg["fav_column_widths"] is None
    assert cfg["hist_column_widths"] is None


def test_base_dir_property_exposed(tmp_path):
    """UserData.base_dir 返回构造时传入的目录路径。"""
    ud = UserData(base_dir=tmp_path)
    assert ud.base_dir == tmp_path

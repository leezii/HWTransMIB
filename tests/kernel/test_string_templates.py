"""StringTemplateStore 测试:按列 OID 精确查预填模板。

容错优先:文件缺失/损坏/某条缺字段都不崩溃,返回空表或跳过该条。
"""
import json

from hwtransmib.kernel.string_templates import StringTemplateStore


def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_lookup_hit(tmp_path):
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.3.6.1.2.1.4.22.1.3", "template": "192.168.1.1"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.3.6.1.2.1.4.22.1.3") == "192.168.1.1"


def test_lookup_miss(tmp_path):
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.3.6.1.2.1.4.22.1.3", "template": "192.168.1.1"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("9.9.9") is None


def test_lookup_miss_when_empty(tmp_path):
    """未 reload 前查询命中 None(构造后内存表为空)。"""
    store = StringTemplateStore(tmp_path / "templates.json")
    assert store.lookup("1.1") is None


def test_missing_file_yields_empty(tmp_path):
    """文件不存在 → 空表,所有 lookup 返回 None,不抛异常。"""
    store = StringTemplateStore(tmp_path / "nope.json")
    store.reload()
    assert store.lookup("1.1") is None


def test_corrupt_json_yields_empty(tmp_path):
    """JSON 非法 → 空表,不崩溃。"""
    f = tmp_path / "templates.json"
    f.write_text("{not valid json", encoding="utf-8")
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") is None


def test_entry_missing_oid_skipped(tmp_path):
    """某条缺 oid → 跳过该条,其余正常加载。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"template": "no-oid-here"},  # 缺 oid,跳过
        {"oid": "1.2", "template": "ok"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.2") == "ok"
    assert store.lookup("no-oid-here") is None


def test_entry_missing_template_skipped(tmp_path):
    """某条缺 template → 跳过该条。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.1"},  # 缺 template,跳过
        {"oid": "1.2", "template": "ok"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") is None
    assert store.lookup("1.2") == "ok"


def test_duplicate_oid_last_wins(tmp_path):
    """重复 OID:数组中后出现的覆盖先出现的。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.1", "template": "first"},
        {"oid": "1.1", "template": "second"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") == "second"


def test_reload_refreshes(tmp_path):
    """reload() 重新读盘:文件中途替换后刷新内存表。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [{"oid": "1.1", "template": "old"}]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") == "old"
    # 替换文件内容
    _write(f, {"templates": [{"oid": "1.1", "template": "new"}]})
    store.reload()
    assert store.lookup("1.1") == "new"


def test_comment_field_ignored(tmp_path):
    """comment 字段不影响匹配/预填(纯标注,程序不使用)。"""
    f = tmp_path / "templates.json"
    _write(f, {"templates": [
        {"oid": "1.1", "template": "tpl", "comment": "just a note"},
    ]})
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") == "tpl"


def test_shape_malformed_json_does_not_crash(tmp_path):
    """合法 JSON 但形状错误(顶层非对象 / 数组元素非对象)→ 不崩溃,返回空表。

    回归: reload() 契约要求任何读取问题都不抛异常。顶层为数组时
    data.get() 会 AttributeError;templates 数组含非 dict 元素时
    entry.get() 会 AttributeError。isinstance 守卫已修复。
    """
    # 顶层是数组(非对象)
    f = tmp_path / "templates.json"
    _write(f, ["not", "an", "object"])
    store = StringTemplateStore(f)
    store.reload()
    assert store.lookup("1.1") is None
    # templates 数组含非 dict 元素
    _write(f, {"templates": ["a-string", 42, None, {"oid": "1.2", "template": "ok"}]})
    store.reload()
    assert store.lookup("1.2") == "ok"
    assert store.lookup("1.1") is None

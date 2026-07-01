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

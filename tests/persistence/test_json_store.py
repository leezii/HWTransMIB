"""JsonStore 测试:原子写入 + 损坏回退。"""
import json
from pathlib import Path

from hwtransmib.persistence.json_store import JsonStore


def test_write_then_read(tmp_path: Path):
    store = JsonStore(tmp_path / "data.json", default={"items": []})
    store.write({"items": [1, 2, 3]})
    assert store.read() == {"items": [1, 2, 3]}


def test_default_when_missing(tmp_path: Path):
    store = JsonStore(tmp_path / "missing.json", default={"a": 1})
    assert store.read() == {"a": 1}


def test_corrupt_file_falls_back_to_default(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{ not valid json")
    store = JsonStore(path, default={"x": 0})
    assert store.read() == {"x": 0}


def test_corrupt_file_is_backed_up(tmp_path: Path):
    path = tmp_path / "bad.json"
    path.write_text("{ broken")
    JsonStore(path, default={})
    backups = list(tmp_path.glob("bad.json.corrupt.*"))
    assert len(backups) == 1


def test_atomic_write_no_partial_file(tmp_path: Path):
    path = tmp_path / "data.json"
    store = JsonStore(path, default={})
    store.write({"k": "v"})
    assert json.loads(path.read_text()) == {"k": "v"}
    # 不应残留临时文件
    assert list(tmp_path.glob("*.tmp")) == []

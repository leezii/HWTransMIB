"""OctetString 预填模板存储:按列 OID 精确查模板。

模板来自外部资源文件(~/.hwtransmib/templates.json),由其他程序生成后
放入目录生效,程序只读不改。文件缺失/损坏均不抛异常,返回空表。
"""
from __future__ import annotations

import json
from pathlib import Path


class StringTemplateStore:
    """按列 OID 精确查预填模板。"""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._table: dict[str, str] = {}

    def reload(self) -> None:
        """重新读盘构建内存表。文件不存在/损坏 → 空表(不抛异常)。"""
        self._table = {}
        try:
            text = self._path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError):
            # OSError: 文件缺失/不可读;ValueError: JSON 非法或非 UTF-8
            # (UnicodeDecodeError/JSONDecodeError 均为 ValueError 子类)。
            # 模板是辅助资源,任何读取问题都不应阻断主流程。
            return
        if not isinstance(data, dict):
            return
        # 重复 OID:后出现的覆盖先出现的(数组写入顺序,后写生效)
        for entry in data.get("templates", []):
            if not isinstance(entry, dict):
                continue
            oid = entry.get("oid")
            template = entry.get("template")
            # 缺 oid 或 template 字段 → 跳过该条
            if not isinstance(oid, str) or not isinstance(template, str):
                continue
            self._table[oid] = template

    def lookup(self, oid: str) -> str | None:
        """按列 OID 精确查模板;未命中返回 None。"""
        return self._table.get(oid)

"""JSON 文件存储,原子写入 + 损坏时备份回退。

写入采用临时文件 + os.replace(原子操作),避免崩溃损坏。
读取时若 JSON 损坏,备份原文件后回退到默认值。
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class JsonStore:
    """单个 JSON 文件的读写封装。"""

    def __init__(self, path: Path, default: dict[str, Any]) -> None:
        self._path = Path(path)
        self._default = default
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self._path.exists():
            return dict(self._default)
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._backup_corrupt()
            return dict(self._default)

    def write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 原子写:同目录临时文件 + os.replace
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), suffix=".tmp",
            prefix=self._path.name + ".",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _backup_corrupt(self) -> None:
        backup = self._path.with_suffix(
            self._path.suffix + f".corrupt.{int(time.time())}"
        )
        try:
            os.replace(self._path, backup)
        except OSError:
            pass

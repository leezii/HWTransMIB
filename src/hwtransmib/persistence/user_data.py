"""用户数据管理:config/imports/favorites/history 四个 JSON 存储。

存储位置: ~/.hwtransmib/ (或测试时指定的 base_dir)。
favorites 按 oid 去重,history 为 LRU(上限可配)。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from hwtransmib.persistence.json_store import JsonStore

_DEFAULT_HISTORY_LIMIT = 200


class UserData:
    """管理用户数据目录下的四个 JSON 文件。"""

    def __init__(self, base_dir: Path | None = None,
                 history_limit: int = _DEFAULT_HISTORY_LIMIT) -> None:
        self._base = Path(base_dir) if base_dir else Path.home() / ".hwtransmib"
        self._limit = history_limit
        self._config = JsonStore(self._base / "config.json", {
            "window_geometry": None,
            "detail_visible": True,
            "split_sizes": None,
            "expanded_oids": [],
            "tree_column_widths": None,
        })
        self._imports = JsonStore(self._base / "imports.json", {"files": []})
        self._favorites = JsonStore(self._base / "favorites.json", {"items": []})
        self._history = JsonStore(self._base / "history.json", {"items": []})

    # --- config ---
    def config(self) -> dict[str, Any]:
        return self._config.read()

    def set_config(self, data: dict[str, Any]) -> None:
        self._config.write(data)

    # --- imports ---
    def imports(self) -> dict[str, Any]:
        return self._imports.read()

    def set_imports(self, files: list[str]) -> None:
        self._imports.write({"files": files})

    # --- favorites ---
    def favorites(self) -> dict[str, Any]:
        return self._favorites.read()

    def add_favorite(self, item: dict[str, Any]) -> None:
        data = self._favorites.read()
        items = [i for i in data["items"] if i.get("oid") != item.get("oid")]
        items.insert(0, item)
        self._favorites.write({"items": items})

    def remove_favorite(self, oid: str) -> None:
        data = self._favorites.read()
        items = [i for i in data["items"] if i.get("oid") != oid]
        self._favorites.write({"items": items})

    # --- history (LRU) ---
    def history(self) -> dict[str, Any]:
        return self._history.read()

    def add_history_entry(self, entry: dict[str, Any]) -> None:
        data = self._history.read()
        items = [e for e in data["items"] if e.get("oid") != entry.get("oid")]
        items.insert(0, entry)
        items = items[: self._limit]
        self._history.write({"items": items})

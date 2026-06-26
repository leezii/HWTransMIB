"""搜索服务:封装 SearchIndex。

防抖由 UI 层用 QTimer 实现(200ms),本服务只负责执行搜索。
"""
from __future__ import annotations

from hwtransmib.kernel.model import MibNode
from hwtransmib.kernel.search_index import SearchIndex


class SearchService:
    """MIB 节点搜索。"""

    def __init__(self, root: MibNode) -> None:
        self._index = SearchIndex(root)

    def rebuild(self, root: MibNode) -> None:
        """重新导入后重建索引。"""
        self._index = SearchIndex(root)

    def search(self, query: str, limit: int = 100) -> list[MibNode]:
        return self._index.search(query, limit=limit)

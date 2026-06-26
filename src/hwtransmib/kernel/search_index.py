"""MIB 节点搜索索引:按名称/OID/描述模糊匹配。

不区分大小写的子串匹配。完整 OID 精确命中优先排在首位。
"""
from __future__ import annotations

from hwtransmib.kernel.model import MibNode


class SearchIndex:
    """对所有节点建立索引,支持名称/OID/描述的子串匹配。"""

    def __init__(self, root: MibNode) -> None:
        self._nodes: list[MibNode] = []
        self._collect(root)

    def _collect(self, node: MibNode) -> None:
        self._nodes.append(node)
        for child in node.children:
            self._collect(child)

    def search(self, query: str, limit: int = 100) -> list[MibNode]:
        """返回匹配节点。完整 OID 精确匹配优先排在首位。"""
        q = query.strip().lower()
        if not q:
            return []
        exact: list[MibNode] = []
        partial: list[MibNode] = []
        raw_query = query.strip()
        for node in self._nodes:
            if node.oid == raw_query:
                exact.append(node)
                continue
            name = node.name.lower()
            oid = node.oid.lower()
            desc = (node.description or "").lower()
            if q in name or q in oid or q in desc:
                partial.append(node)
            if len(exact) + len(partial) >= limit:
                break
        seen = {n.oid for n in exact}
        return exact + [n for n in partial if n.oid not in seen]

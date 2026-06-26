"""MIB 内核领域模型。纯 dataclass,无 Qt 依赖。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    """MIB 节点类型。决定节点能否构造 OID。"""
    MODULE = "module"        # 📦 MIB 模块根
    SUBTREE = "subtree"      # 📁 中间子树节点
    SCALAR = "scalar"        # 🟢 标量(0 索引, OID 固定)
    TABLE = "table"          # 🔴 表对象
    ROW = "row"              # 🔴 表行(entry)
    COLUMN = "column"        # 🟢 表列对象(可构造)


@dataclass
class IndexSpec:
    """表的索引列定义。"""
    column_name: str
    column_oid: str
    implied: bool
    syntax: str


@dataclass
class MibNode:
    """MIB 树中的一个节点。解析完成后视为只读快照。"""
    oid: str
    name: str
    node_type: NodeType
    syntax: str | None = None
    access: str | None = None
    status: str | None = None
    description: str | None = None
    units: str | None = None
    parent: MibNode | None = None
    children: list[MibNode] = field(default_factory=list)
    module_name: str | None = None
    # 仅 TABLE/ROW 节点相关:该表的索引列定义
    index_specs: list[IndexSpec] | None = None

    @property
    def is_constructible(self) -> bool:
        """该节点是否可构造 OID(标量或表列对象)。"""
        return self.node_type in (NodeType.SCALAR, NodeType.COLUMN)

    @property
    def name_path(self) -> list[str]:
        """从根到本节点的名称路径(如 ["ifEntry", "ifDescr"])。"""
        path: list[str] = []
        node: MibNode | None = self
        while node is not None:
            path.append(node.name)
            node = node.parent
        path.reverse()
        return path

    def find(self, oid: str) -> MibNode | None:
        """在本子树中按完整 OID 查找节点。"""
        if self.oid == oid:
            return self
        if not oid.startswith(self.oid + "."):
            return None
        for child in self.children:
            found = child.find(oid)
            if found is not None:
                return found
        return None

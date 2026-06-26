"""从 MibParser 构建 OID 驱动的 MibNode 树,推断节点类型与索引定义。

基于 PySnmp 7.1 探测结果:
- 遍历: get_first_node_name / get_next_node_name,从 iso(1) 开始
- 定位节点: get_node_location(oid) → (module, sym, suffix)
- 节点类型: 按 MRO 类名 MibTable/MibTableRow/MibTableColumn/MibScalar
- 索引: row.indexNames → ((implied, module, name), ...)
"""
from __future__ import annotations

from pysnmp.smi import error

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import IndexSpec, MibNode, NodeType


class MibTreeBuilder:
    """遍历 MibParser 已加载的所有节点,构建 OID 层级树。"""

    def __init__(self, parser: MibParser) -> None:
        self._parser = parser

    def build(self) -> MibNode:
        """返回 OID 树根节点(iso / 1)。"""
        root = MibNode(oid="1", name="iso", node_type=NodeType.SUBTREE)
        view = self._parser.view
        node_cache: dict[str, MibNode] = {"1": root}

        # 从 iso(1) 开始遍历所有节点
        oid, label, _ = view.get_first_node_name()
        # 推进到第一个非根节点
        while True:
            try:
                oid, label, _ = view.get_next_node_name(oid)
            except error.SmiError:
                break
            if not self._add_node(oid, label, root, node_cache):
                break
        return root

    def _add_node(self, oid: tuple[int, ...], label: tuple[str, ...],
                  root: MibNode, cache: dict[str, MibNode]) -> bool:
        """添加一个节点到树。返回 False 表示遍历应停止。"""
        oid_str = ".".join(map(str, oid))
        # 只处理 iso(1) 子树下的节点
        if not oid_str.startswith("1.") and oid_str != "1":
            return True  # 跳过 itu-t(0.x) 等,继续遍历

        name = label[-1] if label else oid_str
        module, sym, syntax, access, status, desc, units, index_specs = (
            self._probe(oid)
        )

        # 找父节点:回溯 OID 直到命中缓存
        parent_oid = ".".join(map(str, oid[:-1]))
        parent = cache.get(parent_oid, root)
        node = MibNode(
            oid=oid_str, name=name, node_type=self._classify(sym),
            syntax=syntax, access=access, status=status, description=desc,
            units=units, parent=parent, module_name=module,
            index_specs=index_specs,
        )
        parent.children.append(node)
        cache[oid_str] = node
        return True

    def _probe(self, oid: tuple[int, ...]):
        """探测节点属性。返回 (module, sym_obj, syntax, access, status, desc, units, index_specs)。"""
        module = None
        sym = None
        syntax = access = status = desc = units = None
        index_specs: list[IndexSpec] | None = None

        try:
            module, sym_name, _ = self._parser.view.get_node_location(oid)
        except error.SmiError:
            return module, sym, syntax, access, status, desc, units, index_specs

        if module and sym_name:
            try:
                (sym,) = self._parser.import_symbols(module, sym_name)
                syntax = self._syntax_name(sym)
                access = self._call(sym, "getMaxAccess")
                status = self._call(sym, "getStatus")
                desc = self._call(sym, "getDescription")
                units = self._call(sym, "getUnits")
                index_specs = self._extract_index_specs(sym)
            except error.SmiError:
                pass
        return module, sym, syntax, access, status, desc, units, index_specs

    def _classify(self, sym) -> NodeType:
        """根据 PySnmp 节点对象类名推断 NodeType。"""
        if sym is None:
            return NodeType.SUBTREE
        mro_names = {cls.__name__ for cls in type(sym).__mro__}
        if "MibTable" in mro_names:
            return NodeType.TABLE
        if "MibTableRow" in mro_names:
            return NodeType.ROW
        if "MibTableColumn" in mro_names:
            return NodeType.COLUMN
        if "MibScalar" in mro_names:
            return NodeType.SCALAR
        return NodeType.SUBTREE

    def _syntax_name(self, sym) -> str | None:
        """安全获取 SYNTAX 类型名(用类名,避免 pyasn1 schema 对象的 bool 异常)。"""
        try:
            syn = sym.getSyntax()
        except Exception:
            return None
        if syn is None:
            return None
        # 用类名作为类型标识,避免触发 pyasn1 schema 对象的 __bool__
        return type(syn).__name__

    def _call(self, sym, method: str) -> str | None:
        fn = getattr(sym, method, None)
        if not callable(fn):
            return None
        try:
            value = fn()
        except Exception:
            return None
        # pyasn1 对象可能在 str() 时触发异常,用 type 名兜底
        try:
            return str(value)
        except Exception:
            return type(value).__name__

    def _extract_index_specs(self, sym) -> list[IndexSpec] | None:
        """从 ROW 节点提取 INDEX 列定义。仅 MibTableRow 有 indexNames。"""
        index_names = getattr(sym, "indexNames", None)
        if not index_names:
            return None
        specs: list[IndexSpec] = []
        for entry in index_names:
            # indexNames 结构: ((implied, module, name), ...)
            implied, mod, col_name = entry[0], entry[1], entry[2]
            col_oid = self._oid_of_symbol(mod, col_name)
            col_syntax = self._syntax_of_symbol(mod, col_name)
            specs.append(IndexSpec(
                column_name=col_name, column_oid=col_oid,
                implied=bool(implied), syntax=col_syntax or "INTEGER",
            ))
        return specs

    def _oid_of_symbol(self, module: str, name: str) -> str:
        try:
            oid, _, _ = self._parser.view.get_node_name((name,), module)
            return ".".join(map(str, oid))
        except error.SmiError:
            return ""

    def _syntax_of_symbol(self, module: str, name: str) -> str | None:
        try:
            (sym,) = self._parser.import_symbols(module, name)
            return self._syntax_name(sym)
        except error.SmiError:
            return None

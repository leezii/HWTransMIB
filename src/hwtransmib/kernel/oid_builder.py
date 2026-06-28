"""OID 构造引擎。复用 PySnmp getInstIdFromIndices 的 SNMP 索引编码能力。

基于探测: row.getInstIdFromIndices(5) 返回 (5,),仅索引后缀(不含 column 前缀)。
拼接规则:
- 标量: base_oid + ".0"
- 表列: base_oid + "." + 索引后缀(由 getInstIdFromIndices 按声明顺序编码)
"""
from __future__ import annotations

from pysnmp.smi import error as smi_error

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import MibNode, NodeType


class OidBuildError(Exception):
    """OID 构造错误。"""


class OidBuilder:
    """构造完整 OID 访问字符串。"""

    def __init__(self, parser: MibParser, root: MibNode) -> None:
        self._parser = parser
        self._root = root

    def build(self, node: MibNode, index_values: dict[str, str]) -> str:
        """构造并返回完整 OID。校验失败抛 OidBuildError。"""
        errors = self.validate(node, index_values)
        if errors:
            raise OidBuildError("; ".join(errors))

        if node.node_type == NodeType.SCALAR:
            return f"{node.oid}.0"
        if node.node_type == NodeType.COLUMN:
            return self._build_column(node, index_values)
        raise OidBuildError(
            f"节点 {node.name} 不可构造(类型 {node.node_type.value})"
        )

    def validate(self, node: MibNode, index_values: dict[str, str]) -> list[str]:
        """返回校验错误列表(空列表表示通过)。"""
        errors: list[str] = []
        if not node.is_constructible:
            errors.append(f"节点 {node.name} 不可构造")
            return errors

        specs = self._row_index_specs(node)
        for spec in specs:
            raw = (index_values.get(spec.column_name, "") or "").strip()
            if raw == "":
                errors.append(f"索引 {spec.column_name} 未填写")
                continue
            errors.extend(self._validate_value(spec, raw))
        return errors

    def _build_column(self, node: MibNode, index_values: dict[str, str]) -> str:
        specs = self._row_index_specs(node)
        row_node = self._row_raw_node(node)
        if row_node is None:
            raise OidBuildError(f"找不到节点 {node.name} 所属的表行定义")

        # 按索引列声明顺序构造类型化值
        typed_values = []
        for spec in specs:
            raw = (index_values.get(spec.column_name, "") or "").strip()
            typed_values.append(self._coerce(spec, raw))

        try:
            inst_id = row_node.getInstIdFromIndices(*typed_values)
        except Exception as exc:
            # Exception 兜底:pyasn1 的 PyAsn1Error 是 Exception 直接子类,
            # 不属于 SmiError,TC 包装类型索引输入非法时会抛出。
            # 这里统一转为友好的 OidBuildError,避免应用崩溃。
            raise OidBuildError(f"索引编码失败: {exc}") from exc

        # getInstIdFromIndices 返回纯索引后缀(不含 column 前缀)
        suffix = ".".join(map(str, tuple(inst_id)))
        return f"{node.oid}.{suffix}" if suffix else node.oid

    def _row_index_specs(self, node: MibNode):
        """沿父链查找所属 ROW 的 index_specs。"""
        parent = node.parent
        while parent is not None:
            if parent.index_specs:
                return parent.index_specs
            parent = parent.parent
        return []

    def _row_raw_node(self, node: MibNode):
        """返回所属 ROW 的 PySnmp 原生节点对象。"""
        ancestor = node.parent
        while ancestor is not None:
            if ancestor.node_type == NodeType.ROW and ancestor.module_name:
                try:
                    (raw,) = self._parser.import_symbols(
                        ancestor.module_name, ancestor.name
                    )
                    return raw
                except smi_error.SmiError:
                    return None
            ancestor = ancestor.parent
        return None

    def _looks_integer(self, spec, raw: str) -> bool:
        """判断索引列是否应为整数。

        优先用 IndexSpec.is_integer(基于 PySnmp 基类链,准确覆盖 TC 包装
        类型如 InetVersion/InterfaceIndex);回退到 syntax 名子串匹配 +
        输入 isdigit 兜底(兼容 is_integer 未填充的旧数据)。
        """
        # 优先:基类判断结果(准确)
        if getattr(spec, "is_integer", False):
            return True
        # 回退:syntax 名子串匹配
        syntax = (spec.syntax or "").upper()
        if "INT" in syntax or "INTEGER" in syntax:
            return True
        # 兜底:输入是纯数字时按整数处理
        return raw.lstrip("-").isdigit()

    def _coerce(self, spec, raw: str):
        """将字符串输入转为 PySnmp 期望的索引值类型。"""
        if self._looks_integer(spec, raw):
            try:
                return int(raw)
            except ValueError:
                raise OidBuildError(
                    f"{spec.column_name} 需要整数,得到 {raw!r}"
                )
        # 字符串/IP/MAC 直接传字符串,PySnmp 按 INDEX syntax 编码
        return raw

    def _validate_value(self, spec, raw: str) -> list[str]:
        if self._looks_integer(spec, raw):
            try:
                int(raw)
            except ValueError:
                return [f"{spec.column_name} 需要整数,得到 {raw!r}"]
        return []

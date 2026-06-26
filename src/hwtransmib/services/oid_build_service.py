"""OID 构造服务:构造 + 记录历史。

组合 OidBuilder 与 UserData 的历史记录。
UI 层只与此服务打交道,不直接碰内核 OidBuilder。
"""
from __future__ import annotations

import time

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import MibNode
from hwtransmib.kernel.oid_builder import OidBuildError, OidBuilder
from hwtransmib.persistence.user_data import UserData


class OidBuildService:
    """组合 OidBuilder 与历史记录。"""

    def __init__(self, parser: MibParser, root: MibNode,
                 user_data: UserData) -> None:
        self._builder = OidBuilder(parser=parser, root=root)
        self._ud = user_data

    @property
    def builder(self) -> OidBuilder:
        """暴露 OidBuilder 供 UI 实时预览使用(不记录历史)。"""
        return self._builder

    def validate(self, node: MibNode,
                 index_values: dict[str, str]) -> list[str]:
        return self._builder.validate(node, index_values)

    def build(self, node: MibNode, index_values: dict[str, str]) -> str:
        """构造 OID,但不记录历史(用于实时预览)。"""
        return self._builder.build(node, index_values)

    def build_and_record(self, node: MibNode,
                         index_values: dict[str, str]) -> str:
        """构造并记录到历史。用于"复制 OID"操作。"""
        oid = self._builder.build(node, index_values)
        self._ud.add_history_entry({
            "oid": oid,
            "name": node.name,
            "module": node.module_name,
            "timestamp": int(time.time()),
        })
        return oid

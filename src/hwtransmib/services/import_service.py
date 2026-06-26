"""导入编排服务:从文件路径解析 MIB,构建树,返回报告。

MIB 文件名通常即模块名(IF-MIB → 模块 "IF-MIB")。
文件所在目录加入 PySnmp 搜索路径,自动补依赖。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.model import MibNode
from hwtransmib.kernel.tree_builder import MibTreeBuilder


@dataclass
class ImportReport:
    """一次导入的结果。"""
    loaded_modules: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    node_count: int = 0


class ImportService:
    """MIB 文件导入服务。"""

    def __init__(self, extra_sources: list[str] | None = None) -> None:
        self._sources = list(extra_sources or [])
        self._parser: MibParser | None = None
        self._root: MibNode | None = None

    def import_files(self, file_paths: list[str]) -> ImportReport:
        report = ImportReport()
        source_dirs: set[str] = set(self._sources)
        module_names: list[str] = []
        for fp in file_paths:
            path = Path(fp)
            if not path.exists():
                report.errors.append(f"文件不存在: {fp}")
                continue
            source_dirs.add(str(path.parent))
            module_names.append(self._module_name_of(path))

        self._parser = MibParser(extra_sources=list(source_dirs))
        result = self._parser.parse(module_names)
        report.loaded_modules = result.loaded_modules
        report.errors.extend(result.errors)
        if result.loaded_modules:
            self._root = MibTreeBuilder(self._parser).build()
            report.node_count = self._count(self._root)
        return report

    def get_root(self) -> MibNode:
        if self._root is None:
            raise RuntimeError("尚未导入任何 MIB")
        return self._root

    def get_parser(self) -> MibParser:
        if self._parser is None:
            raise RuntimeError("尚未导入任何 MIB")
        return self._parser

    def _module_name_of(self, path: Path) -> str:
        """从文件名提取 MIB 模块名(去扩展名和版本后缀)。"""
        name = path.name
        name = re.split(r"[.](txt|mib|my)$", name, flags=re.IGNORECASE)[0]
        return name

    def _count(self, node: MibNode) -> int:
        return 1 + sum(self._count(c) for c in node.children)

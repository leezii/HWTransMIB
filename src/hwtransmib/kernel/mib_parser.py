"""封装 PySnmp 7.1 MibBuilder/MibViewController,提供 MIB 解析与查询能力。

API 基于 PySnmp 7.1 真实探测:
- b.add_mib_sources(builder.DirMibSource(path))  加载本地目录
- compiler.add_mib_compiler(b)                   注册编译器(自动纳入 builder sources)
- b.load_modules(name)                           加载(自动拓扑排序补依赖)
- view.MibViewController(b).get_node_name(oid)   按 OID 查名称
"""
from __future__ import annotations

from dataclasses import dataclass, field

from pysnmp.smi import builder, compiler, error, view


class MibParseError(Exception):
    """MIB 解析相关错误。"""


@dataclass
class ParseResult:
    """一次解析的结果。"""
    loaded_modules: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class MibParser:
    """封装 PySnmp 的 MIB 加载与查询。

    extra_sources: MIB 文件搜索目录(含标准库 + 用户目录)。
    """

    def __init__(self, extra_sources: list[str] | None = None) -> None:
        self._builder = builder.MibBuilder()
        for src in extra_sources or []:
            self._builder.add_mib_sources(builder.DirMibSource(src))
        compiler.add_mib_compiler(self._builder)
        self._view: view.MibViewController | None = None
        self._loaded: set[str] = set()

    def parse(self, module_names: list[str]) -> ParseResult:
        """加载给定 MIB 模块(自动按依赖顺序补齐)。部分失败不中断。"""
        result = ParseResult()
        for name in module_names:
            try:
                self._builder.load_modules(name)
                self._loaded.add(name)
                result.loaded_modules.append(name)
            except error.MibNotFoundError as exc:
                result.errors.append(f"模块 {name} 未找到(可能依赖缺失): {exc}")
            except error.SmiError as exc:
                result.errors.append(f"模块 {name} 解析失败: {exc}")
        if self._loaded:
            self._view = view.MibViewController(self._builder)
        return result

    def is_loaded(self, module_name: str) -> bool:
        return module_name in self._loaded

    @property
    def view(self) -> view.MibViewController:
        if self._view is None:
            raise MibParseError("尚未加载任何 MIB 模块")
        return self._view

    @property
    def builder(self) -> builder.MibBuilder:
        """暴露 builder 供 TreeBuilder/OidBuilder 内省使用。"""
        return self._builder

    def get_oid_by_name(self, name: str, module: str | None = None) -> str:
        """根据节点名查询完整 OID。

        PySnmp 7.1 get_node_name 签名: get_node_name(nodeName, modName="")。
        nodeName 是名称路径元组,modName 限定模块。
        """
        try:
            oid, _, _ = self.view.get_node_name((name,), module or "")
        except error.SmiError as exc:
            raise MibParseError(f"找不到节点 {name}: {exc}") from exc
        return ".".join(map(str, oid))

    def import_symbols(self, module: str, symbol: str):
        """导入模块符号(返回 PySnmp 原生节点对象列表)。"""
        return self._builder.import_symbols(module, symbol)

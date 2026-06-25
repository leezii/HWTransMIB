"""封装 PySnmp 7.1 MibBuilder/MibViewController,提供 MIB 解析与查询能力。

关键: PySnmp 的 DirMibSource 只加载已编译的 .py 文件,不会自动编译纯文本
MIB 源文件。本模块在 parse() 中先用 PySMI 的 MibCompiler 把纯文本 MIB
(含内置标准 MIB 作依赖)统一编译到输出目录,再加载。

正确编译方案(基于探测,避开 PyFileBorrower 的 EXTENSION_SUFFIXES 缺陷):
- 把内置标准 MIB 纯文本目录 + 用户 MIB 目录都作为 FileReader source
- 用 StubSearcher(不依赖已编译缓存,全部重新编译)
- mc.compile(...) 统一编译标准 + 私有 MIB 及其依赖
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from pysmi.codegen.pysnmp import PySnmpCodeGen
from pysmi.compiler import MibCompiler
from pysmi.parser.smiv2 import SmiV2Parser
from pysmi.reader.localfile import FileReader
from pysmi.searcher.stub import StubSearcher
from pysmi.writer.pyfile import PyFileWriter
from pysnmp.smi import builder, compiler, error, view


class MibParseError(Exception):
    """MIB 解析相关错误。"""


@dataclass
class ParseResult:
    """一次解析的结果。"""
    loaded_modules: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _bundled_standard_mibs_dir() -> str:
    """随包分发的内置标准 MIB 纯文本目录。

    作为编译依赖来源(SNMPv2-SMI/TC 等),让私有 MIB 的 imports 能解析。
    """
    here = Path(__file__).resolve().parent
    candidate = here / "standard_mibs"
    return str(candidate)


class MibParser:
    """封装 PySnmp 的 MIB 加载与查询。

    extra_sources: MIB 文件搜索目录(用户私有 MIB 目录)。
    """

    def __init__(self, extra_sources: list[str] | None = None) -> None:
        self._sources = list(extra_sources or [])
        self._builder = builder.MibBuilder()
        compiler.add_mib_compiler(self._builder)
        self._view: view.MibViewController | None = None
        self._loaded: set[str] = set()
        # 已编译输出目录(parse 时动态创建)
        self._compile_out: str | None = None

    def parse(self, module_names: list[str]) -> ParseResult:
        """加载给定 MIB 模块(自动编译纯文本源文件 + 按依赖顺序补齐)。

        部分失败不中断。
        """
        result = ParseResult()
        if not module_names:
            return result

        # 1. 先用 PySMI MibCompiler 编译纯文本 MIB(含标准依赖)→ .py
        self._compile_plain_text(module_names, result)

        # 2. 再用 builder 加载编译产物
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

    def _compile_plain_text(self, module_names: list[str],
                            result: ParseResult) -> None:
        """用 PySMI MibCompiler 编译纯文本 MIB(标准 + 私有)到输出目录。

        把内置标准 MIB 纯文本目录 + 用户目录都作为 FileReader source,
        让编译器统一编译,私有 MIB 的标准依赖(SNMPv2-SMI 等)能被解析。
        避开 PyFileBorrower 的 EXTENSION_SUFFIXES 只找 .so 的缺陷。
        """
        out_dir = tempfile.mkdtemp(prefix="hwtransmib_compile_")
        self._compile_out = out_dir

        mc = MibCompiler(SmiV2Parser(), PySnmpCodeGen(), PyFileWriter(out_dir))
        # 内置标准 MIB 纯文本目录作依赖来源
        std_dir = _bundled_standard_mibs_dir()
        if Path(std_dir).is_dir():
            mc.add_sources(FileReader(std_dir))
        # 用户私有 MIB 目录
        for src in self._sources:
            mc.add_sources(FileReader(src))
        # StubSearcher: 不依赖已编译缓存,全部重新编译
        mc.add_searchers(StubSearcher())

        compiled = mc.compile(*module_names)
        for name, status in compiled.items():
            status_str = str(status)
            # 仅用户请求的模块失败才记录错误(标准依赖被顺带编译不算)
            if name in module_names and "fail" in status_str.lower():
                err = getattr(status, "error", None)
                result.errors.append(
                    f"模块 {name} 编译失败: {err or status_str}"
                )

        # 把编译产物目录加入 builder 搜索路径
        self._builder.add_mib_sources(builder.DirMibSource(out_dir))

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


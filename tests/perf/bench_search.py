"""搜索性能基准:测量大 MIB 下的单次搜索耗时。

判断是否需要优化(YAGNI):
- < 50ms: 当前可接受,无需优化
- >= 50ms: 需实现哈希/前缀索引

用法: uv run python tests/perf/bench_search.py
"""
import statistics
import time

from hwtransmib.kernel.mib_parser import MibParser
from hwtransmib.kernel.search_index import SearchIndex
from hwtransmib.kernel.tree_builder import MibTreeBuilder


def _walk(node):
    yield node
    for c in node.children:
        yield from _walk(c)


def main():
    mibs_dir = "tests/fixtures/mibs"
    std_dir = "src/hwtransmib/kernel/standard_mibs"
    parser = MibParser(extra_sources=[mibs_dir, std_dir])
    parser.parse(["IF-MIB"])
    root = MibTreeBuilder(parser).build()

    index = SearchIndex(root)
    node_count = sum(1 for _ in _walk(root))
    print(f"节点数: {node_count}")

    queries = ["if", "Descr", "2.2.1.2", "table", "interface", "MIB"]
    timings = []
    for q in queries:
        for _ in range(100):
            t0 = time.perf_counter()
            index.search(q)
            timings.append(time.perf_counter() - t0)

    avg_ms = statistics.mean(timings) * 1000
    p95_ms = sorted(timings)[int(len(timings) * 0.95)] * 1000
    print(f"平均: {avg_ms:.2f}ms")
    print(f"P95:  {p95_ms:.2f}ms")
    if avg_ms < 50:
        print("结论: <50ms,当前性能可接受,无需优化(YAGNI)")
    else:
        print("结论: >=50ms,建议实现哈希/前缀索引")


if __name__ == "__main__":
    main()

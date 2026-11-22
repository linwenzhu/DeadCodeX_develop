"""Demonstrate explicit project entry points without CLI integration."""

from deadcodex import DeadCodex


def main():
    analyzer = DeadCodex()
    analyzer.scan(
        "def helper():\n    pass\n"
        "def worker():\n    helper()\n"
        "def old():\n    pass\n",
        "workers.py",
    )
    analyzer.scan("from workers import worker\nworker()\n", "app.py")
    result = analyzer.analyze_reachability(["app"])
    for edge in analyzer.call_graph.edges:
        print(f"{edge.caller} -> {edge.callee}")
    print(result.explain("workers.helper"))
    unused = analyzer.get_unused_code_project(["app"])
    assert {str(item.qualified_name) for item in unused} == {"workers.old"}
    print("unused:", ", ".join(str(item.qualified_name) for item in unused))


if __name__ == "__main__":
    main()

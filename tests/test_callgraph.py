from deadcodex import core
from deadcodex.model import ResolutionStatus


def _write(path, source):
    path.write_text(source, encoding="utf-8")


def _edges(analyzer):
    return {
        (str(edge.caller), str(edge.callee))
        for edge in analyzer.call_graph.edges
    }


def test_builds_local_function_call_edges():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "def helper():\n    pass\ndef main():\n    helper()\nmain()\n",
        filename="module.py",
    )

    call_graph = analyzer.resolve_references()

    assert _edges(analyzer) == {
        ("module", "module.main"),
        ("module.main", "module.helper"),
    }
    assert call_graph is analyzer.call_graph
    assert all(
        call.status is ResolutionStatus.RESOLVED
        for call in analyzer.call_graph.calls
    )


def test_builds_cross_module_call_edge(tmp_path):
    _write(tmp_path / "a.py", "def worker():\n    pass\n")
    _write(tmp_path / "b.py", "from a import worker\nworker()\n")
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])
    analyzer.resolve_references()

    assert _edges(analyzer) == {("b", "a.worker")}


def test_static_method_edge_and_unresolved_instance_call():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "class Service:\n"
        "    def helper(self):\n"
        "        pass\n"
        "    def run(self):\n"
        "        self.helper()\n"
        "Service.run(None)\n",
        filename="module.py",
    )

    analyzer.resolve_references()

    assert _edges(analyzer) == {
        ("module", "module.Service.run"),
    }

    dynamic = next(
        c
        for c in analyzer.call_graph.calls
        if c.callee_parts == ("self", "helper")
    )
    assert dynamic.status is ResolutionStatus.UNRESOLVED


def test_keeps_external_and_dynamic_calls_without_local_edges():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "import os\nos.getcwd()\nfactory()()\n", filename="module.py"
    )

    analyzer.resolve_references()

    assert analyzer.call_graph.edges == []
    assert analyzer.call_graph_builder.status_counts == {
        ResolutionStatus.EXTERNAL: 1,
        ResolutionStatus.UNRESOLVED: 2,
    }


def test_call_graph_does_not_change_default_unused_result():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "def first():\n    pass\ndef second():\n    pass\nfirst()\n",
        filename="module.py",
    )

    analyzer.resolve_references()

    assert [item.name for item in analyzer.unused_funcs] == ["second"]
    assert _edges(analyzer) == {("module", "module.first")}

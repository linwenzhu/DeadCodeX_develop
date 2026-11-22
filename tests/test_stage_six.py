import pytest

from deadcodex import DeadCodex
from deadcodex.callgraph import CallGraphBuilder, ReachabilityAnalyzer
from deadcodex.model import CallGraph, QualifiedName, ResolutionStatus


def test_unknown_call_protects_possible_target_and_transitive_callees():
    analyzer = DeadCodex()
    analyzer.scan(
        "def helper():\n    pass\n"
        "def run():\n    helper()\n"
        "def dead():\n    pass\n",
        "provider.py",
    )
    analyzer.scan("run()\n", "app.py")

    unused = analyzer.get_unused_code_project(["app"])

    assert {str(item.qualified_name) for item in unused} == {"provider.dead"}
    assert analyzer.project_reachability.explain("provider.run").startswith(
        "unreachable from"
    )


def test_shadowed_import_does_not_produce_a_call_edge():
    analyzer = DeadCodex()
    analyzer.scan("def run():\n    pass\n", "provider.py")
    analyzer.scan(
        "import provider as service\n"
        "def handle(service):\n    service.run()\n",
        "app.py",
    )
    assert analyzer.resolve_references().edges == []
    assert all(call.target is None for call in analyzer.call_graph.calls)


def test_non_callable_reference_is_not_a_resolved_call():
    analyzer = DeadCodex()
    analyzer.scan("value = 1\nvalue()\n", "app.py")
    graph = analyzer.resolve_references()

    assert graph.edges == []
    assert graph.calls[0].status is ResolutionStatus.UNRESOLVED
    assert graph.calls[0].target is None


def test_rebuilding_call_graph_does_not_duplicate_edges():
    analyzer = DeadCodex()
    analyzer.scan("def helper():\n    pass\nhelper()\n", "app.py")
    first = analyzer.resolve_references()
    second = analyzer.resolve_references()

    assert first is not second
    assert first.edges == second.edges
    assert len(second.edges) == 1


def test_function_entry_and_confidence_filter():
    analyzer = DeadCodex()
    analyzer.scan("def main():\n    pass\ndef dead():\n    pass\n", "app.py")
    entry = QualifiedName.from_string("app.main")

    unused = analyzer.get_unused_code_project([entry])
    assert {item.name for item in unused} == {"dead"}
    assert analyzer.get_unused_code_project([entry], min_confidence=100) == []
    assert analyzer.analyze_reachability([entry]).path_to(entry) == (entry,)


def test_entry_order_does_not_change_deterministic_path():
    analyzer = DeadCodex()
    analyzer.scan(
        "def target():\n    pass\n"
        "def first():\n    target()\n"
        "def second():\n    target()\n",
        "app.py",
    )
    paths = [
        analyzer.analyze_reachability(entries).path_to("app.target")
        for entries in [
            ["app.first", "app.second"],
            ["app.second", "app.first"],
        ]
    ]
    assert paths[0] == paths[1]
    assert tuple(map(str, paths[0])) == ("app.first", "app.target")


def test_graph_builders_work_without_the_core_orchestrator():
    analyzer = DeadCodex()
    analyzer.scan("def helper():\n    pass\nhelper()\n", "app.py")
    analyzer.resolve_references()
    graph = CallGraphBuilder().build(analyzer.project, analyzer.defined_items)
    result = ReachabilityAnalyzer().analyze(
        analyzer.project, analyzer.defined_items, graph, ["app"]
    )
    assert isinstance(graph, CallGraph)
    assert result.unreachable == frozenset()


@pytest.mark.parametrize("confidence", [-1, 101])
def test_project_analysis_rejects_out_of_range_confidence(confidence):
    with pytest.raises(ValueError, match="between 0 and 100"):
        DeadCodex().get_unused_code_project(["app"], confidence)

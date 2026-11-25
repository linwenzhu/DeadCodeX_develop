import ast
from pathlib import Path

from deadcodex import core
from deadcodex.analysis import AnalysisResult
from deadcodex.collector import AstCollector
from deadcodex.model import DEFAULT_CONFIDENCE, Item
from deadcodex.parser import PythonParser


def test_core_keeps_legacy_exports_and_node_visitor_contract():
    assert core.Item is Item
    assert core.DEFAULT_CONFIDENCE == DEFAULT_CONFIDENCE
    assert issubclass(core.DeadCodex, ast.NodeVisitor)


def test_parser_builds_module_context():
    module = PythonParser().parse(
        "unused = 1  # noqa: V107\n", filename="example.py"
    )

    assert module.filename == Path("example.py")
    assert module.source_lines == ["unused = 1  # noqa: V107"]
    assert module.noqa_lines["V107"] == {1}
    assert module.module is None
    assert isinstance(module.tree, ast.Module)
    assert module.error is None


def test_parser_returns_invalid_source_with_its_context():
    module = PythonParser().parse("\x00", filename="broken.py")

    assert module.filename == Path("broken.py")
    assert module.tree is None
    # CPython 3.12+ raises SyntaxError for null bytes, while older supported
    # versions raise ValueError. PythonParser intentionally accepts both.
    assert isinstance(module.error, (SyntaxError, ValueError))


def test_collector_can_run_without_the_core_orchestrator():
    module = PythonParser().parse(
        "def used():\n    pass\n\nused()\ndef unused():\n    pass\n",
        filename="example.py",
    )
    collector = AstCollector()

    collector.collect(module)

    assert [item.name for item in collector.unused_funcs] == ["unused"]


def test_analysis_result_filters_used_items():
    result = AnalysisResult()
    result.defined_funcs.extend(
        [
            Item("used", "function", Path("a.py"), 1, 1),
            Item("unused", "function", Path("a.py"), 2, 4),
        ]
    )
    result.used_names.add("used")

    assert [item.name for item in result.get_unused_code()] == ["unused"]

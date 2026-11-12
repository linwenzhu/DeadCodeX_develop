import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from deadcodex import DeadCodex
from deadcodex.reachability import Reachability


def collect_reports(source):
    reports = []
    analysis = Reachability(report=lambda **report: reports.append(report))

    class Visitor(ast.NodeVisitor):
        def generic_visit(self, node):
            super().generic_visit(node)
            analysis.visit(node)

    Visitor().visit(ast.parse(textwrap.dedent(source)))
    return reports


@pytest.mark.parametrize(
    ("source", "name", "first", "last"),
    [
        ("def f():\n    return\n    x = 1\n    y = 2\n", "return", 3, 4),
        ("raise RuntimeError()\nx = 1\ny = 2\n", "raise", 2, 3),
        ("while flag:\n    break\n    x = 1\n", "break", 3, 3),
        ("while flag:\n    continue\n    x = 1\n", "continue", 3, 3),
    ],
)
def test_standalone_callback_reports_the_complete_dead_region(
    source, name, first, last
):
    reports = collect_reports(source)

    assert len(reports) == 1
    report = reports[0]
    assert report["name"] == name
    assert report["first_node"].lineno == first
    assert report["last_node"].lineno == last
    assert report["message"] == f"unreachable code after '{name}'"


def test_reset_clears_flow_state_without_replacing_the_callback():
    reports = []
    analysis = Reachability(report=lambda **report: reports.append(report))
    tree = ast.parse("raise RuntimeError()\nx = 1\n")
    analysis.visit(tree.body[0])
    analysis.visit(tree)
    assert len(reports) == 1

    analysis.reset()
    reports.clear()
    analysis.visit(tree)
    assert reports == []
    analysis.visit(tree.body[0])
    analysis.visit(tree)
    assert len(reports) == 1


@pytest.mark.parametrize(
    "source",
    [
        "def f(flag):\n    if flag:\n        return\n    value = 1\n",
        "def f():\n    def inner():\n        return\n    value = 1\n",
        "while True:\n    if flag:\n        break\nvalue = 1\n",
    ],
)
def test_possible_execution_paths_are_not_reported_as_unreachable(source):
    assert collect_reports(source) == []


def test_collector_converts_callback_to_high_confidence_item():
    analyzer = DeadCodex()
    analyzer.scan("def f():\n    return\n    value = 1\n", "sample.py")
    findings = [
        item
        for item in analyzer.get_unused_code(min_confidence=100)
        if item.typ == "unreachable_code"
    ]

    assert len(findings) == 1
    finding = findings[0]
    assert finding.filename == Path("sample.py")
    assert (finding.first_lineno, finding.last_lineno) == (3, 3)
    assert finding.confidence == 100
    assert finding.message == "unreachable code after 'return'"


def test_module_flow_state_is_reset_after_syntax_error(capsys):
    analyzer = DeadCodex()
    analyzer.scan("def broken(:\n", "broken.py")
    analyzer.scan(
        "def valid(flag):\n    if flag:\n        return\n    x = 1\n",
        "valid.py",
    )

    assert analyzer.unreachable_code == []
    assert "broken.py" in capsys.readouterr().err


def test_stage_d_demo_runs_without_cli_integration():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "examples/stage_d/run_demo.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "7 scenarios passed" in result.stdout

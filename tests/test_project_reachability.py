import pytest

from deadcodex import core
from deadcodex.model import QualifiedName, ResolutionStatus


def _write(path, source):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _names(items, item_type="function"):
    return {
        str(item.qualified_name) for item in items if item.typ == item_type
    }


def test_finds_reachable_path_and_unreachable_callable():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "def helper():\n"
        "    pass\n"
        "def main():\n"
        "    helper()\n"
        "def dead():\n"
        "    pass\n"
        "main()\n",
        filename="module.py",
    )

    result = analyzer.analyze_reachability(["module"])

    assert result.entry_points == {QualifiedName.from_string("module")}
    assert {str(name) for name in result.reachable} == {
        "module",
        "module.main",
        "module.helper",
    }
    assert {str(name) for name in result.unreachable} == {"module.dead"}
    assert tuple(map(str, result.path_to("module.helper"))) == (
        "module",
        "module.main",
        "module.helper",
    )
    assert result.path_to("module.dead") == ()
    assert result.explain("module.helper") == (
        "reachable via module -> module.main -> module.helper"
    )
    assert result.explain("module.dead") == (
        "unreachable from entry points: module"
    )


def test_handles_recursive_calls_and_multiple_entry_points():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "def left():\n"
        "    right()\n"
        "def right():\n"
        "    left()\n"
        "def other():\n"
        "    pass\n",
        filename="module.py",
    )

    result = analyzer.analyze_reachability(["module.left", "module.other"])

    assert {str(name) for name in result.reachable} == {
        "module.left",
        "module.right",
        "module.other",
    }
    assert result.unreachable == set()


def test_marks_missing_and_duplicate_entry_points(tmp_path):
    _write(tmp_path / "first" / "duplicate.py", "def first():\n    pass\n")
    _write(tmp_path / "second" / "duplicate.py", "def second():\n    pass\n")
    analyzer = core.DeadCodex()
    analyzer.scavenge(
        [
            tmp_path / "first" / "duplicate.py",
            tmp_path / "second" / "duplicate.py",
        ]
    )

    result = analyzer.analyze_reachability(["missing", "duplicate"])

    assert {str(name) for name in result.unresolved_entry_points} == {
        "missing"
    }
    assert {str(name) for name in result.ambiguous_entry_points} == {
        "duplicate"
    }
    assert analyzer.project_reachability_analyzer.status_counts == {
        ResolutionStatus.RESOLVED: 0,
        ResolutionStatus.UNRESOLVED: 1,
        ResolutionStatus.AMBIGUOUS: 1,
    }
    assert result.explain("missing") == "unresolved entry point: missing"
    assert result.explain("duplicate") == "ambiguous entry point: duplicate"
    assert result.explain("other") == "unknown project target: other"


def test_project_unused_result_distinguishes_same_named_functions(tmp_path):
    _write(tmp_path / "a.py", "def run():\n    pass\n")
    _write(tmp_path / "b.py", "def run():\n    pass\n")
    _write(tmp_path / "app.py", "from a import run\nrun()\n")
    analyzer = core.DeadCodex()
    analyzer.scavenge([tmp_path])

    project_unused = analyzer.get_unused_code_project(["app"])

    assert analyzer.unused_funcs == []
    assert _names(project_unused) == {"b.run"}


def test_project_unused_result_keeps_unresolved_call_name_conservative(
    tmp_path,
):
    _write(tmp_path / "a.py", "def run():\n    pass\n")
    _write(tmp_path / "b.py", "def run():\n    pass\n")
    _write(tmp_path / "app.py", "run()\n")
    analyzer = core.DeadCodex()
    analyzer.scavenge([tmp_path])

    project_unused = analyzer.get_unused_code_project(["app"])

    assert _names(project_unused) == set()


def test_project_unused_result_rejects_invalid_entry_points():
    analyzer = core.DeadCodex()
    analyzer.scan("def function():\n    pass\n", filename="module.py")

    with pytest.raises(ValueError, match="Invalid or ambiguous entry points"):
        analyzer.get_unused_code_project(["missing"])

    with pytest.raises(ValueError, match="between 0 and 100"):
        analyzer.get_unused_code_project(["module"], min_confidence=101)


def test_reachability_requires_an_entry_point():
    analyzer = core.DeadCodex()
    analyzer.scan("def function():\n    pass\n", filename="module.py")

    with pytest.raises(ValueError, match="At least one entry point"):
        analyzer.analyze_reachability([])

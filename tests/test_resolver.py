from deadcodex import core
from deadcodex.model import ImportKind, ResolutionStatus


def _write(path, source=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _module(project, name):
    matches = project.modules_named(name)
    assert len(matches) == 1
    return matches[0]


def _binding(project, module_name, bound_name):
    module = _module(project, module_name)
    matches = [
        binding
        for binding in module.imports
        if binding.bound_name == bound_name
    ]
    assert len(matches) == 1
    return matches[0]


def test_resolves_absolute_project_module_and_symbol_imports(tmp_path):
    _write(tmp_path / "a.py", "def function():\n    pass\n")
    _write(
        tmp_path / "b.py",
        "import a as module_a\nfrom a import function as imported_function\n",
    )
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    module_binding = _binding(analyzer.project, "b", "module_a")
    assert module_binding.kind is ImportKind.MODULE
    assert module_binding.status is ResolutionStatus.RESOLVED
    assert str(module_binding.target) == "a"
    symbol_binding = _binding(analyzer.project, "b", "imported_function")
    assert symbol_binding.kind is ImportKind.SYMBOL
    assert symbol_binding.status is ResolutionStatus.RESOLVED
    assert str(symbol_binding.target) == "a.function"


def test_resolves_relative_symbol_module_and_star_imports(tmp_path):
    _write(tmp_path / "package" / "__init__.py")
    _write(tmp_path / "package" / "a.py", "value = 1\n")
    _write(
        tmp_path / "package" / "b.py",
        "from .a import value\nfrom . import a\nfrom .a import *\n",
    )
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    value = _binding(analyzer.project, "package.b", "value")
    assert value.status is ResolutionStatus.RESOLVED
    assert str(value.target) == "package.a.value"
    module_a = _binding(analyzer.project, "package.b", "a")
    assert module_a.status is ResolutionStatus.RESOLVED
    assert str(module_a.target) == "package.a"
    star = _binding(analyzer.project, "package.b", "*")
    assert star.status is ResolutionStatus.RESOLVED
    assert str(star.target) == "package.a"


def test_marks_external_and_unresolved_imports(tmp_path):
    _write(tmp_path / "package" / "__init__.py")
    _write(
        tmp_path / "package" / "module.py",
        "import os\n"
        "from requests import get\n"
        "from .missing import value\n"
        "from package import absent\n",
    )
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    assert _binding(analyzer.project, "package.module", "os").status is (
        ResolutionStatus.EXTERNAL
    )
    assert _binding(analyzer.project, "package.module", "get").status is (
        ResolutionStatus.EXTERNAL
    )
    assert _binding(analyzer.project, "package.module", "value").status is (
        ResolutionStatus.UNRESOLVED
    )
    assert _binding(analyzer.project, "package.module", "absent").status is (
        ResolutionStatus.UNRESOLVED
    )


def test_marks_duplicate_project_modules_as_ambiguous(tmp_path):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write(first_root / "duplicate.py", "value = 1\n")
    _write(second_root / "duplicate.py", "value = 2\n")
    _write(tmp_path / "consumer.py", "import duplicate\n")
    analyzer = core.DeadCodex()

    analyzer.scavenge([first_root, second_root, tmp_path / "consumer.py"])

    duplicate = _binding(analyzer.project, "consumer", "duplicate")
    assert duplicate.status is ResolutionStatus.AMBIGUOUS
    assert duplicate.target is None


def test_standalone_scan_can_be_resolved_explicitly():
    analyzer = core.DeadCodex()
    analyzer.scan("import external_dependency\n", filename="module.py")

    pending = _binding(analyzer.project, "module", "external_dependency")
    assert pending.status is ResolutionStatus.PENDING

    analyzer.resolve_imports()

    assert pending.status is ResolutionStatus.EXTERNAL
    assert analyzer.import_resolver.status_counts == {
        ResolutionStatus.EXTERNAL: 1
    }


def test_reexports_resolve_to_the_defining_module(tmp_path):
    _write(tmp_path / "pkg" / "__init__.py", "from .api import public\n")
    _write(
        tmp_path / "pkg" / "api" / "__init__.py",
        "from ..worker import actual as public\n",
    )
    _write(tmp_path / "pkg" / "worker.py", "def actual():\n    pass\n")
    _write(
        tmp_path / "main.py",
        "from pkg import public as run\nimport pkg\n"
        "def main():\n    run()\n    pkg.public()\n",
    )
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    assert str(_binding(analyzer.project, "main", "run").target) == (
        "pkg.worker.actual"
    )
    assert [
        str(edge.callee)
        for edge in analyzer.call_graph.edges
        if str(edge.caller) == "main.main"
    ] == ["pkg.worker.actual", "pkg.worker.actual"]


def test_circular_reexports_remain_unresolved(tmp_path):
    _write(tmp_path / "a" / "__init__.py", "from b import callback\n")
    _write(tmp_path / "b" / "__init__.py", "from a import callback\n")
    _write(tmp_path / "main.py", "from a import callback\ncallback()\n")
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    assert all(
        _binding(analyzer.project, module, "callback").status
        is ResolutionStatus.UNRESOLVED
        for module in ("a", "b", "main")
    )
    assert analyzer.call_graph.edges == []

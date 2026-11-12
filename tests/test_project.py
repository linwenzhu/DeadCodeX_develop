import pytest

from deadcodex import core
from deadcodex.model import QualifiedName, ScopeKind
from deadcodex.parser import PythonParser
from deadcodex.project import ProjectLoader
from deadcodex.scope import ScopeCollector


def _make_package(tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "module.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "script.py").write_text("result = 2\n", encoding="utf-8")
    return package


def test_qualified_name_supports_parent_and_child_operations():
    name = QualifiedName.from_string("package.module")

    assert str(name) == "package.module"
    assert name.name == "module"
    assert name.parent == QualifiedName(("package",))
    assert str(name.child("function")) == "package.module.function"


@pytest.mark.parametrize("value", ["", ".module", "module."])
def test_qualified_name_rejects_empty_parts(value):
    with pytest.raises(ValueError):
        QualifiedName.from_string(value)


def test_project_loader_discovers_modules_and_package_names(tmp_path):
    package = _make_package(tmp_path)

    project = ProjectLoader().load([tmp_path])

    assert project.root == tmp_path.resolve()
    assert {module.name for module in project.modules} == {
        "package",
        "package.module",
        "script",
    }
    package_module = project.module_for_path(package / "__init__.py")
    assert package_module.name == "package"
    assert package_module.is_package


def test_package_directory_is_resolved_from_its_parent(tmp_path):
    package = _make_package(tmp_path)

    project = ProjectLoader().load([package])

    assert project.root == tmp_path.resolve()
    assert {module.name for module in project.modules} == {
        "package",
        "package.module",
    }


def test_project_loader_reads_discovered_module(tmp_path):
    _make_package(tmp_path)
    loader = ProjectLoader()
    project = loader.load([tmp_path])

    module = project.module_for_path(tmp_path / "script.py")

    assert loader.read_module(module) == "result = 2\n"


def test_scope_collector_builds_qualified_nested_scopes(tmp_path):
    source = """\
class Service:
    async def run(self):
        def callback():
            pass
"""
    module = ProjectLoader().module_from_path(
        tmp_path / "package" / "module.py", source_root=tmp_path
    )
    parsed_module = PythonParser().parse(
        source, filename=module.path, module=module
    )

    ScopeCollector().collect(module, parsed_module.tree)

    service = module.scope.children[0]
    run = service.children[0]
    callback = run.children[0]
    assert service.kind is ScopeKind.CLASS
    assert str(service.qualified_name) == "package.module.Service"
    assert run.kind is ScopeKind.FUNCTION
    assert str(run.qualified_name) == "package.module.Service.run"
    assert str(callback.qualified_name) == (
        "package.module.Service.run.callback"
    )
    assert callback.parent is run


def test_deadcodex_exposes_project_metadata_without_changing_results(tmp_path):
    _make_package(tmp_path)
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    assert {module.name for module in analyzer.project.modules} == {
        "package",
        "package.module",
        "script",
    }
    assert {item.name for item in analyzer.unused_vars} == {"result", "value"}
    assert {str(item.qualified_name) for item in analyzer.unused_vars} == {
        "package.module.value",
        "script.result",
    }


def test_same_symbol_name_gets_distinct_module_qualified_names(tmp_path):
    (tmp_path / "a.py").write_text("def run():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def run():\n    pass\n", encoding="utf-8")
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    assert {str(item.qualified_name) for item in analyzer.defined_funcs} == {
        "a.run",
        "b.run",
    }


def test_repeated_scavenge_accumulates_project_modules(tmp_path):
    _write_first = tmp_path / "first.py"
    _write_second = tmp_path / "second.py"
    _write_first.write_text("first = 1\n", encoding="utf-8")
    _write_second.write_text("second = 2\n", encoding="utf-8")
    analyzer = core.DeadCodex()

    analyzer.scavenge([_write_first])
    analyzer.scavenge([_write_second])

    assert {module.name for module in analyzer.project.modules} == {
        "first",
        "second",
    }

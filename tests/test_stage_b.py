import ast
from pathlib import Path

import pytest

from deadcodex.analysis import AnalysisResult
from deadcodex.model import (
    CallSite,
    Finding,
    ImportBinding,
    ImportKind,
    Item,
    ModuleModel,
    ProjectModel,
    QualifiedName,
    ScopeKind,
    UsageKind,
    UsageReference,
)
from deadcodex.project import ProjectLoader
from deadcodex.scope import ScopeCollector


@pytest.mark.parametrize("parts", [(), ("",), ("pkg", "")])
def test_qualified_name_rejects_invalid_parts(parts):
    with pytest.raises(ValueError):
        QualifiedName(parts)


@pytest.mark.parametrize("child", ["", "nested.name"])
def test_qualified_name_rejects_invalid_child(child):
    with pytest.raises(ValueError):
        QualifiedName(("pkg",)).child(child)


def test_module_reset_clears_facts_and_preserves_identity(tmp_path):
    module = ProjectLoader().module_from_path(tmp_path / "sample.py")
    tree = ast.parse("def run():\n    return 1\n")
    ScopeCollector().collect(module, tree)
    module.imports.append(
        ImportBinding(ImportKind.MODULE, "os", "os", None, 0, 1)
    )
    module.references.append(
        UsageReference(
            UsageKind.NAME,
            "run",
            ("run",),
            module.qualified_name,
            module.path,
            1,
        )
    )
    module.calls.append(
        CallSite(module.qualified_name, ("run",), module.path, 1)
    )

    module.reset_analysis()

    assert module.name == "sample"
    assert module.scope.kind is ScopeKind.MODULE
    assert module.scope.children == []
    assert module.scope_by_node_id == {}
    assert module.imports == module.references == module.calls == []


def test_module_facts_are_not_shared(tmp_path):
    loader = ProjectLoader()
    first = loader.module_from_path(tmp_path / "first.py")
    second = loader.module_from_path(tmp_path / "second.py")
    first.scope.add_child("run", ScopeKind.FUNCTION)

    assert second.scope.children == []
    assert first.imports is not second.imports
    assert first.references is not second.references
    assert first.calls is not second.calls


def test_scope_lookup_and_node_mapping(tmp_path):
    module = ProjectLoader().module_from_path(tmp_path / "sample.py")
    tree = ast.parse("class Service:\n    def run(self):\n        value = 1\n")
    ScopeCollector().collect(module, tree)
    method = module.scope_named("sample.Service.run")

    assert method.parent is module.scope_named("sample.Service")
    assert module.scope_for_node(tree.body[0].body[0].body[0]) is method
    assert module.scope_named("sample.missing") is None
    assert module.scope_for_node(ast.Constant(1)) is module.scope


def test_project_include_and_path_lookup(tmp_path):
    loader = ProjectLoader()
    first = loader.module_from_path(tmp_path / "a" / "module.py")
    second = loader.module_from_path(tmp_path / "b" / "module.py")
    project = ProjectModel(tmp_path / "a")
    assert project.add_module(first) is first
    added = project.include(ProjectModel(tmp_path / "b", [second]))

    assert project.root == tmp_path
    assert added == [second]
    assert project.module_for_path(first.path) is first
    assert project.module_for_path(tmp_path / "missing.py") is None
    assert project.modules_named("module") == [first, second]


def test_empty_project_and_in_memory_module():
    loader = ProjectLoader()
    assert loader.load([]).modules == []
    module = loader.in_memory_module()
    assert module.name == "<memory>"
    assert isinstance(module, ModuleModel)


def test_analysis_filters_confidence_and_sorts_results():
    result = AnalysisResult()
    low = Item("small", "function", Path("b.py"), 1, 1)
    high = Item("large", "function", Path("a.py"), 2, 5, confidence=100)
    used = Item("used", "function", Path("a.py"), 1, 1)
    result.defined_funcs.extend([low, high, used, high])
    result.used_names.add("used")

    assert result.get_unused_code() == [high, low]
    assert result.get_unused_code(sort_by_size=True) == [low, high]
    assert result.get_unused_code(min_confidence=100) == [high]


@pytest.mark.parametrize("confidence", [-1, 101])
def test_analysis_rejects_invalid_confidence(confidence):
    with pytest.raises(ValueError):
        AnalysisResult().get_unused_code(min_confidence=confidence)


def test_finding_preserves_item_location_and_qualified_name():
    item = Item(
        "run",
        "function",
        Path("sample.py"),
        2,
        4,
        qualified_name=QualifiedName(("sample", "run")),
    )
    finding = Finding.from_item(item)

    assert finding.to_dict() == {
        "name": "run",
        "qualified_name": "sample.run",
        "kind": "function",
        "filename": "sample.py",
        "first_lineno": 2,
        "last_lineno": 4,
        "size": 3,
        "message": "unused function 'run'",
        "confidence": 60,
    }
    assert "60% confidence, 3 lines" in item.get_report(add_size=True)

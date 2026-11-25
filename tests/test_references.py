from deadcodex import core
from deadcodex.model import ResolutionStatus, UsageKind


def _write(path, source):
    path.write_text(source, encoding="utf-8")


def _reference(analyzer, module_name, parts):
    module = analyzer.project.modules_named(module_name)[0]
    matches = [
        reference
        for reference in module.references
        if reference.parts == parts
    ]
    assert len(matches) == 1
    return matches[0]


def test_collects_and_resolves_lexical_name_references():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "def function(argument):\n    local = argument\n    return local\n",
        filename="module.py",
    )

    analyzer.resolve_references()

    argument = _reference(analyzer, "module", ("argument",))
    assert argument.kind is UsageKind.NAME
    assert argument.status is ResolutionStatus.RESOLVED
    assert str(argument.target) == "module.function.argument"
    local = _reference(analyzer, "module", ("local",))
    assert local.status is ResolutionStatus.RESOLVED
    assert str(local.target) == "module.function.local"


def test_resolves_import_alias_and_module_attribute_references(tmp_path):
    _write(tmp_path / "a.py", "def function():\n    pass\n")
    _write(
        tmp_path / "b.py",
        "import a as module_a\n"
        "from a import function as imported_function\n"
        "module_a.function()\n"
        "imported_function()\n",
    )
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    module_alias = _reference(analyzer, "b", ("module_a",))
    assert module_alias.status is ResolutionStatus.RESOLVED
    assert str(module_alias.target) == "a"
    assert str(module_alias.local_binding_name) == "b.module_a"
    attribute = _reference(analyzer, "b", ("module_a", "function"))
    assert attribute.kind is UsageKind.ATTRIBUTE
    assert attribute.status is ResolutionStatus.RESOLVED
    assert str(attribute.target) == "a.function"
    imported_function = _reference(analyzer, "b", ("imported_function",))
    assert imported_function.status is ResolutionStatus.RESOLVED
    assert str(imported_function.target) == "a.function"
    assert str(imported_function.local_binding_name) == "b.imported_function"


def test_function_scope_does_not_resolve_bare_class_attributes():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "class Service:\n"
        "    value = 1\n"
        "    def read(self):\n"
        "        return value\n",
        filename="module.py",
    )

    analyzer.resolve_references()

    value = _reference(analyzer, "module", ("value",))
    assert value.status is ResolutionStatus.UNRESOLVED
    assert value.target is None


def test_qualified_unused_result_distinguishes_same_named_functions(tmp_path):
    _write(tmp_path / "a.py", "def run():\n    pass\n")
    _write(tmp_path / "b.py", "def run():\n    pass\n")
    _write(tmp_path / "consumer.py", "from a import run\nrun()\n")
    analyzer = core.DeadCodex()

    analyzer.scavenge([tmp_path])

    assert analyzer.unused_funcs == []
    qualified_unused = analyzer.get_unused_code(qualified=True)
    assert [
        str(item.qualified_name)
        for item in qualified_unused
        if item.typ == "function"
    ] == ["b.run"]
    assert not [item for item in qualified_unused if item.typ == "import"]
    references = [
        reference
        for module in analyzer.project.modules
        for reference in module.references
    ]
    assert analyzer.get_unused_code_qualified(references) == qualified_unused


def test_qualified_unused_result_keeps_legacy_dynamic_name_fallback():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "class Service:\n"
        "    dynamic_attribute = 1\n"
        "getattr(Service, 'dynamic_attribute')\n",
        filename="module.py",
    )

    qualified_unused = analyzer.get_unused_code(qualified=True)

    assert "dynamic_attribute" not in {item.name for item in qualified_unused}


def test_resolves_static_class_method_attribute():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "class Service:\n    def run(self):\n        pass\nService.run\n",
        filename="module.py",
    )

    analyzer.resolve_references()

    run = _reference(analyzer, "module", ("Service", "run"))
    assert run.status is ResolutionStatus.RESOLVED
    assert str(run.target) == "module.Service.run"

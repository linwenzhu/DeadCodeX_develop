from pathlib import Path

import pytest

from deadcodex import DeadCodex
from deadcodex.model import ModuleModel, QualifiedName, ResolutionStatus


def scan_module(analyzer, name, source):
    module = ModuleModel(
        path=Path(name.replace(".", "/") + ".py"),
        qualified_name=QualifiedName.from_string(name),
        source_root=Path(),
    )
    analyzer.project.add_module(module)
    analyzer.scan(source, module=module)
    return module


def test_parameter_shadows_module_import():
    analyzer = DeadCodex()
    scan_module(analyzer, "provider", "def run():\n    pass\n")
    consumer = scan_module(
        analyzer,
        "consumer",
        "import provider as service\n"
        "def handle(service):\n    return service.run()\n",
    )
    analyzer.resolve_references()
    reference = next(
        r for r in consumer.references if r.parts == ("service", "run")
    )
    assert reference.target != QualifiedName.from_string("provider.run")


def test_unimported_symbol_from_another_module_stays_unresolved():
    analyzer = DeadCodex()
    scan_module(analyzer, "provider", "def hidden():\n    pass\n")
    consumer = scan_module(analyzer, "consumer", "hidden()\n")
    analyzer.resolve_references()
    reference = next(r for r in consumer.references if r.parts == ("hidden",))
    assert reference.status is ResolutionStatus.UNRESOLVED
    assert reference.target is None


def test_local_class_attribute_keeps_the_member_suffix():
    analyzer = DeadCodex()
    consumer = scan_module(
        analyzer,
        "consumer",
        "class Service:\n"
        "    @staticmethod\n    def run():\n        pass\n"
        "Service.run()\n",
    )
    analyzer.resolve_references()
    reference = next(
        r for r in consumer.references if r.parts == ("Service", "run")
    )
    assert reference.target == QualifiedName.from_string(
        "consumer.Service.run"
    )


def test_relative_import_cannot_escape_top_level_package():
    analyzer = DeadCodex()
    scan_module(analyzer, "tools", "def run():\n    pass\n")
    consumer = scan_module(
        analyzer,
        "pkg.consumer",
        "from ..tools import run\nrun()\n",
    )
    analyzer.resolve_references()
    assert consumer.imports[0].status is ResolutionStatus.UNRESOLVED
    assert consumer.imports[0].target is None


@pytest.mark.parametrize(
    "source",
    [
        "import provider as service\n"
        "def handle():\n    service = object()\n    return service.run()\n",
        "import provider as service\n"
        "def outer(service):\n"
        "    def inner():\n        return service.run()\n",
    ],
)
def test_local_and_closure_bindings_shadow_imports(source):
    analyzer = DeadCodex()
    scan_module(analyzer, "provider", "def run():\n    pass\n")
    consumer = scan_module(analyzer, "consumer", source)
    analyzer.resolve_references()
    reference = next(
        r for r in consumer.references if r.parts == ("service", "run")
    )
    assert reference.status is ResolutionStatus.UNRESOLVED
    assert reference.target is None
    assert reference.binding_target is None


def test_function_import_does_not_leak_to_siblings_or_module():
    analyzer = DeadCodex()
    scan_module(analyzer, "provider", "def run():\n    pass\n")
    consumer = scan_module(
        analyzer,
        "consumer",
        "def first():\n    from provider import run\n    run()\n"
        "def second():\n    run()\nrun()\n",
    )
    analyzer.resolve_references()
    references = [r for r in consumer.references if r.parts == ("run",)]
    assert [r.status for r in references] == [
        ResolutionStatus.RESOLVED,
        ResolutionStatus.UNRESOLVED,
        ResolutionStatus.UNRESOLVED,
    ]
    assert consumer.imports[0].scope_name == QualifiedName.from_string(
        "consumer.first"
    )


def test_method_does_not_capture_class_namespace_import():
    analyzer = DeadCodex()
    scan_module(analyzer, "provider", "def run():\n    pass\n")
    consumer = scan_module(
        analyzer,
        "consumer",
        "class Service:\n    from provider import run\n"
        "    def method(self):\n        return run()\n",
    )
    analyzer.resolve_references()
    reference = next(r for r in consumer.references if r.parts == ("run",))
    assert reference.status is ResolutionStatus.UNRESOLVED


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "import provider as service\nservice = object()\nservice.run()\n",
            ResolutionStatus.UNRESOLVED,
        ),
        (
            "service = object()\nimport provider as service\nservice.run()\n",
            ResolutionStatus.RESOLVED,
        ),
    ],
)
def test_same_scope_rebinding_respects_statement_order(source, expected):
    analyzer = DeadCodex()
    scan_module(analyzer, "provider", "def run():\n    pass\n")
    consumer = scan_module(analyzer, "consumer", source)
    analyzer.resolve_references()
    reference = next(
        r for r in consumer.references if r.parts == ("service", "run")
    )
    assert reference.status is expected


def test_valid_parent_relative_import_is_preserved():
    analyzer = DeadCodex()
    scan_module(analyzer, "pkg.tools", "def run():\n    pass\n")
    consumer = scan_module(
        analyzer,
        "pkg.sub.consumer",
        "from ..tools import run\nrun()\n",
    )
    analyzer.resolve_references()
    assert consumer.imports[0].status is ResolutionStatus.RESOLVED
    assert consumer.imports[0].target == QualifiedName.from_string(
        "pkg.tools.run"
    )


def test_duplicate_project_modules_remain_ambiguous():
    analyzer = DeadCodex()
    scan_module(analyzer, "provider", "def run():\n    pass\n")
    scan_module(analyzer, "provider", "def run():\n    pass\n")
    consumer = scan_module(
        analyzer,
        "consumer",
        "from provider import run\nrun()\n",
    )
    analyzer.resolve_references()
    assert consumer.imports[0].status is ResolutionStatus.AMBIGUOUS
    assert consumer.references[0].status is ResolutionStatus.AMBIGUOUS

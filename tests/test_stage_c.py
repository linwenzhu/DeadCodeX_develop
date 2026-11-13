from pathlib import Path

from deadcodex.core import DeadCodex
from deadcodex.model import (
    ImportBinding,
    ImportKind,
    Item,
    ModuleModel,
    ProjectModel,
    QualifiedName,
    ResolutionStatus,
    UsageKind,
    UsageReference,
)
from deadcodex.resolver import ImportResolver, ReferenceResolver


def make_module(name, path=None):
    module_path = Path(path or f"{name.replace('.', '/')}.py")
    return ModuleModel(
        path=module_path,
        qualified_name=QualifiedName.from_string(name),
        source_root=Path(),
    )


def make_definition(owner, name, line=1):
    return Item(
        name=name,
        typ="function",
        filename=owner.path,
        first_lineno=line,
        last_lineno=line,
        qualified_name=owner.qualified_name.child(name),
    )


def make_reference(owner, *parts, line=10):
    return UsageReference(
        kind=UsageKind.NAME if len(parts) == 1 else UsageKind.ATTRIBUTE,
        name=parts[-1],
        parts=parts,
        scope_name=owner.qualified_name,
        filename=owner.path,
        first_lineno=line,
    )


def test_resolves_absolute_module_import_and_alias_reference():
    tools = make_module("pkg.tools")
    work = make_definition(tools, "work")
    consumer = make_module("app.main")
    consumer.imports.append(
        ImportBinding(
            kind=ImportKind.MODULE,
            bound_name="tools",
            module_name="pkg.tools",
            imported_name=None,
            level=0,
            alias="tools",
            first_lineno=1,
        )
    )
    consumer.references.append(make_reference(consumer, "tools", "work"))
    project = ProjectModel(Path(), [tools, consumer])

    ImportResolver([work]).resolve(project)
    ReferenceResolver([work]).resolve(project)

    binding = consumer.imports[0]
    reference = consumer.references[0]
    assert binding.status is ResolutionStatus.RESOLVED
    assert binding.target == QualifiedName.from_string("pkg.tools")
    assert reference.status is ResolutionStatus.RESOLVED
    assert reference.binding_target == binding.target
    assert reference.target == QualifiedName.from_string("pkg.tools.work")


def test_resolves_relative_symbol_import_and_alias():
    package = make_module("pkg", "pkg/__init__.py")
    tools = make_module("pkg.tools")
    work = make_definition(tools, "work")
    consumer = make_module("pkg.service")
    consumer.imports.append(
        ImportBinding(
            kind=ImportKind.SYMBOL,
            bound_name="run",
            module_name="tools",
            imported_name="work",
            level=1,
            alias="run",
            first_lineno=1,
        )
    )
    consumer.references.append(make_reference(consumer, "run"))
    project = ProjectModel(Path(), [package, tools, consumer])

    ReferenceResolver([work]).resolve(project)

    assert consumer.imports[0].status is ResolutionStatus.RESOLVED
    assert consumer.references[0].status is ResolutionStatus.RESOLVED
    assert consumer.references[0].target == QualifiedName.from_string(
        "pkg.tools.work"
    )


def test_marks_external_and_unresolved_imports_separately():
    consumer = make_module("pkg.service")
    external = ImportBinding(
        kind=ImportKind.SYMBOL,
        bound_name="get",
        module_name="requests",
        imported_name="get",
        level=0,
        alias=None,
        first_lineno=1,
    )
    missing = ImportBinding(
        kind=ImportKind.SYMBOL,
        bound_name="lost",
        module_name="missing",
        imported_name="lost",
        level=1,
        alias=None,
        first_lineno=2,
    )
    consumer.imports.extend((external, missing))
    consumer.references.extend(
        (
            make_reference(consumer, "get", line=3),
            make_reference(consumer, "lost", line=4),
        )
    )
    project = ProjectModel(Path(), [consumer])

    ReferenceResolver().resolve(project)

    assert external.status is ResolutionStatus.EXTERNAL
    assert consumer.references[0].status is ResolutionStatus.EXTERNAL
    assert consumer.references[0].target == QualifiedName.from_string(
        "requests.get"
    )
    assert missing.status is ResolutionStatus.UNRESOLVED
    assert consumer.references[1].status is ResolutionStatus.UNRESOLVED


def test_same_name_symbols_are_ambiguous_without_an_import():
    first = make_module("first")
    second = make_module("second")
    definitions = [
        make_definition(first, "shared"),
        make_definition(second, "shared"),
    ]
    consumer = make_module("consumer")
    consumer.references.append(make_reference(consumer, "shared"))
    project = ProjectModel(Path(), [first, second, consumer])

    ReferenceResolver(definitions).resolve(project)

    reference = consumer.references[0]
    assert reference.status is ResolutionStatus.AMBIGUOUS
    assert reference.target is None


def test_module_import_without_alias_resolves_from_bound_root():
    tools = make_module("pkg.tools")
    work = make_definition(tools, "work")
    consumer = make_module("consumer")
    consumer.imports.append(
        ImportBinding(
            kind=ImportKind.MODULE,
            bound_name="pkg",
            module_name="pkg.tools",
            imported_name=None,
            level=0,
            alias=None,
            first_lineno=1,
        )
    )
    consumer.references.append(
        make_reference(consumer, "pkg", "tools", "work")
    )
    project = ProjectModel(Path(), [tools, consumer])

    ReferenceResolver([work]).resolve(project)

    assert consumer.references[0].status is ResolutionStatus.RESOLVED
    assert consumer.references[0].target == QualifiedName.from_string(
        "pkg.tools.work"
    )


def test_core_resolves_collected_imports_and_references(tmp_path):
    (tmp_path / "provider.py").write_text(
        "def run():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "consumer.py").write_text(
        "from provider import run as execute\nresult = execute()\n",
        encoding="utf-8",
    )
    analyzer = DeadCodex()
    analyzer.scavenge([tmp_path])

    analyzer.resolve_imports()
    analyzer.resolve_references()

    consumer = analyzer.project.module_for_path(tmp_path / "consumer.py")
    binding = consumer.imports[0]
    reference = next(
        item for item in consumer.references if item.name == "execute"
    )
    assert binding.status is ResolutionStatus.RESOLVED
    assert binding.target == QualifiedName.from_string("provider.run")
    assert reference.status is ResolutionStatus.RESOLVED
    assert reference.target == QualifiedName.from_string("provider.run")

from pathlib import Path

from deadcodex.collector import AstCollector
from deadcodex.core import DeadCodex
from deadcodex.model import ModuleModel, QualifiedName
from deadcodex.parser import PythonParser
from deadcodex.utils import ExitCode, get_modules, read_file


def make_module(name="sample"):
    return ModuleModel(
        path=Path(f"{name}.py"),
        qualified_name=QualifiedName((name,)),
        source_root=Path(),
    )


def test_parser_builds_ast_context_and_noqa_metadata():
    module = make_module()
    parsed = PythonParser().parse(
        "value = 1  # noqa: F841\n", "sample.py", module
    )

    assert parsed.module is module
    assert parsed.tree is not None
    assert parsed.error is None
    assert parsed.source_lines == ["value = 1  # noqa: F841"]
    assert parsed.noqa_lines["V107"] == {1}


def test_parser_returns_invalid_source_with_context():
    module = make_module("broken")
    parsed = PythonParser().parse("def broken(:\n", "broken.py", module)

    assert parsed.module is module
    assert parsed.tree is None
    assert isinstance(parsed.error, SyntaxError)


def test_collector_records_definitions_imports_references_and_calls():
    module = make_module()
    source = """
import os.path as osp
from collections import defaultdict as dd

class Service:
    @classmethod
    def build(cls, value):
        result = osp.join(str(value), "x")
        return dd(list, output=result)
""".lstrip()
    parsed = PythonParser().parse(source, module.path, module)

    analyzer = DeadCodex()
    analyzer.scan(source, module=module)

    assert {item.name for item in analyzer.defined_imports} == {"osp", "dd"}
    assert {item.name for item in analyzer.defined_classes} == {"Service"}
    assert {item.name for item in analyzer.defined_methods} == {"build"}
    assert {item.name for item in analyzer.defined_vars} >= {
        "cls",
        "value",
        "result",
    }
    assert {binding.bound_name for binding in module.imports} == {"osp", "dd"}
    assert {reference.name for reference in module.references} >= {
        "join",
        "str",
        "value",
        "dd",
        "result",
    }
    assert {call.callee_parts for call in module.calls} >= {
        ("osp", "join"),
        ("str",),
        ("dd",),
    }
    assert parsed.tree is not None


def test_collector_can_run_without_core_orchestrator():
    module = make_module()
    source = "def used():\n    pass\n\nused()\ndef unused():\n    pass\n"
    parsed = PythonParser().parse(source, module.path, module)
    analyzer = AstCollector()

    analyzer.collect(parsed)

    assert {item.name for item in analyzer.unused_funcs} == {"unused"}


def test_scan_collects_unreachable_code_and_scope_metadata():
    analyzer = DeadCodex()
    analyzer.scan(
        "class Service:\n"
        "    def run(self):\n"
        "        return 1\n"
        "        unreachable = 2\n",
        "service.py",
    )

    module = analyzer.project.module_for_path("service.py")
    assert module is not None
    assert module.scope.children[0].qualified_name == QualifiedName(
        ("service", "Service")
    )
    assert any(
        item.typ == "unreachable_code" for item in analyzer.get_unused_code()
    )


def test_scan_reports_syntax_errors(capsys):
    analyzer = DeadCodex()
    analyzer.scan("def broken(:\n", "broken.py")

    assert analyzer.exit_code == ExitCode.InvalidInput
    assert "broken.py:1" in capsys.readouterr().err


def test_scavenge_discovers_files_excludes_paths_and_loads_whitelist(tmp_path):
    included = tmp_path / "included.py"
    excluded = tmp_path / "excluded.py"
    included.write_text("import ast\nanswer = 42\n", encoding="utf-8")
    excluded.write_text("ignored = True\n", encoding="utf-8")

    analyzer = DeadCodex()
    analyzer.scavenge([tmp_path], exclude=["excluded.py"])

    project_paths = {module.path for module in analyzer.project.modules}
    assert included.resolve() in project_paths
    assert excluded.resolve() in project_paths
    assert "ignored" not in {item.name for item in analyzer.defined_vars}
    assert "visit_Call" in analyzer.used_names
    assert set(get_modules([tmp_path])) == {
        excluded.resolve(),
        included.resolve(),
    }


def test_read_file_honours_python_encoding_cookie(tmp_path):
    source = tmp_path / "encoded.py"
    source.write_bytes(
        "# coding: latin-1\nname = 'caf\xe9'\n".encode("latin-1")
    )

    assert "café" in read_file(source)

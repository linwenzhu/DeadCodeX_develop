"""Regression tests for the qualified analysis and analysis pipeline."""

import pytest

from deadcodex import DeadCodex, ProjectAnalyzer


def analyze(files):
    analyzer = DeadCodex()
    for filename, source in files:
        analyzer.scan(source, filename)
    return analyzer


@pytest.mark.parametrize(
    "other_source",
    [
        "def public():\n    pass\npublic()\n",
        "from external import public as alias\n",
    ],
    ids=["ordinary-reference", "alias-original-name"],
)
def test_export_remains_used_when_other_module_has_same_name(other_source):
    analyzer = analyze(
        [
            ("a.py", 'def public():\n    pass\n__all__ = ["public"]\n'),
            ("b.py", other_source),
        ]
    )
    unused = analyzer.get_unused_code(qualified=True)
    assert "a.public" not in {str(item.qualified_name) for item in unused}


def test_getattr_use_survives_same_named_resolved_method_in_other_module():
    analyzer = analyze(
        [
            (
                "a.py",
                "class Service:\n    def run(self):\n        pass\n"
                'getattr(Service, "run")\n',
            ),
            (
                "b.py",
                "class Other:\n    def run(self):\n        pass\n"
                "Other.run(None)\n",
            ),
        ]
    )
    unused = analyzer.get_unused_code(qualified=True)
    assert "a.Service.run" not in {str(item.qualified_name) for item in unused}


@pytest.mark.parametrize("external", [False, True], ids=["local", "external"])
def test_parameter_attribute_use_does_not_mark_outer_import_used(external):
    files = (
        [("app.py", "import os\ndef handle(os):\n    os.getcwd()\n")]
        if external
        else [
            ("provider.py", "def run():\n    pass\n"),
            (
                "app.py",
                "import provider as service\n"
                "def handle(service):\n    service.run()\n",
            ),
        ]
    )
    analyzer = analyze(files)
    unused_imports = {
        item.name
        for item in analyzer.get_unused_code(qualified=True)
        if item.typ == "import"
    }
    assert ("os" if external else "service") in unused_imports


def test_qualified_same_named_functions_remain_independent():
    analyzer = analyze(
        [
            ("a.py", "def run():\n    pass\n"),
            ("b.py", "def run():\n    pass\n"),
            ("app.py", "from a import run\nrun()\n"),
        ]
    )
    assert {
        str(item.qualified_name)
        for item in analyzer.get_unused_code(qualified=True)
    } == {"b.run"}
    assert analyzer.get_unused_code() == []


def test_genuine_import_use_stays_used():
    analyzer = analyze([("app.py", "import os\nos.getcwd()\n")])
    assert analyzer.get_unused_code(qualified=True) == []


def test_alias_declaration_does_not_count_as_symbol_use():
    analyzer = analyze(
        [
            ("a.py", "def run():\n    pass\n"),
            ("app.py", "from a import run as start\n"),
        ]
    )
    assert {
        str(item.qualified_name)
        for item in analyzer.get_unused_code(qualified=True)
    } == {"a.run", "app.start"}


def test_unresolved_attribute_still_counts_as_use_of_its_import():
    analyzer = analyze([("a.py", ""), ("app.py", "import a\na.unknown()\n")])
    assert analyzer.get_unused_code(qualified=True) == []


def test_only_the_selected_import_declaration_counts_as_used():
    analyzer = analyze(
        [("app.py", "import os as lib\nimport sys as lib\nlib.exit()\n")]
    )
    assert [
        (item.name, item.first_lineno)
        for item in analyzer.get_unused_code(qualified=True)
    ] == [("lib", 1)]


@pytest.mark.parametrize(
    "expression", ['"%(value)s" % locals()', '"{value}".format(**locals())']
)
def test_format_string_use_survives_same_named_static_read(expression):
    analyzer = analyze(
        [
            ("a.py", f"value = 1\nprint({expression})\n"),
            ("b.py", "value = 2\nprint(value)\n"),
        ]
    )
    assert analyzer.get_unused_code(qualified=True) == []


def test_pipeline_repeated_runs_rebuild_graph_and_support_generator_inputs():
    analyzer = analyze([("app.py", "def run():\n    pass\nrun()\n")])
    pipeline = ProjectAnalyzer()
    first = pipeline.analyze(
        analyzer.project, iter(analyzer.defined_items), iter(["app"])
    )
    second = pipeline.analyze(analyzer.project, analyzer.defined_items)
    assert first.call_graph.edges == second.call_graph.edges
    assert len(second.call_graph.edges) == 1
    assert first.reachability.unreachable == frozenset()
    assert second.reachability is None

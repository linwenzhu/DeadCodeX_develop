import pytest

from deadcodex import (
    DecoratorEntryPointAdapter,
    FastAPIAdapter,
    FlaskAdapter,
    core,
)
from deadcodex.adapters import make_framework_adapter


def test_collected_items_retain_decorator_names():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "@route\n@router.get('/')\ndef endpoint():\n    pass\n",
        filename="module.py",
    )

    endpoint = analyzer.defined_funcs[0]

    assert endpoint.decorators == ("@route", "@router.get")


def test_decorator_adapter_discovers_reachable_framework_entry_point():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "@router.get('/')\n"
        "def endpoint():\n"
        "    helper()\n"
        "def helper():\n"
        "    pass\n"
        "def dead():\n"
        "    pass\n",
        filename="module.py",
    )
    adapter = DecoratorEntryPointAdapter(("router.*",))

    result = analyzer.analyze_reachability(entry_point_providers=[adapter])

    assert {str(name) for name in result.entry_points} == {"module.endpoint"}
    assert {str(name) for name in result.reachable} == {
        "module.endpoint",
        "module.helper",
    }
    assert {str(name) for name in result.unreachable} == {"module.dead"}


def test_project_unused_api_accepts_explicit_and_discovered_entries():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "@job\n"
        "def background():\n"
        "    pass\n"
        "def command():\n"
        "    pass\n"
        "def dead():\n"
        "    pass\n",
        filename="module.py",
    )
    adapter = DecoratorEntryPointAdapter(("@job",))

    unused = analyzer.get_unused_code_project(
        ["module.command"], entry_point_providers=[adapter]
    )

    assert {
        str(item.qualified_name) for item in unused if item.typ == "function"
    } == {"module.dead"}


def test_decorator_adapter_requires_patterns_and_matches():
    with pytest.raises(ValueError, match="decorator pattern"):
        DecoratorEntryPointAdapter(())

    analyzer = core.DeadCodex()
    analyzer.scan("def function():\n    pass\n", filename="module.py")

    with pytest.raises(ValueError, match="At least one entry point"):
        analyzer.analyze_reachability(
            entry_point_providers=[DecoratorEntryPointAdapter(("route",))]
        )


def test_flask_and_fastapi_adapters_only_discover_their_handlers():
    analyzer = core.DeadCodex()
    analyzer.scan(
        "@app.route('/')\n"
        "def flask_handler():\n"
        "    pass\n"
        "@router.websocket('/events')\n"
        "def socket_handler():\n"
        "    pass\n"
        "@pytest.fixture\n"
        "def fixture():\n"
        "    pass\n",
        filename="module.py",
    )

    flask_entries = FlaskAdapter().discover(
        analyzer.project, analyzer.defined_items
    )
    fastapi_entries = FastAPIAdapter().discover(
        analyzer.project, analyzer.defined_items
    )

    assert {str(name) for name in flask_entries} == {"module.flask_handler"}
    assert {str(name) for name in fastapi_entries} == {"module.socket_handler"}


def test_framework_adapter_factory():
    assert isinstance(make_framework_adapter("flask"), FlaskAdapter)
    assert isinstance(make_framework_adapter("fastapi"), FastAPIAdapter)
    with pytest.raises(ValueError, match="Unknown framework"):
        make_framework_adapter("django")

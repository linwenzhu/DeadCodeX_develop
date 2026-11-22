"""Tests for the framework and decorator entry point adapters."""

import pytest

from deadcodex import (
    DecoratorEntryPointAdapter,
    FastAPIAdapter,
    FlaskAdapter,
    core,
)
from deadcodex.adapters import make_framework_adapter


def test_collected_items_retain_decorator_names():
    """Scanned callables keep decorator names so adapters can match them."""
    analyzer = core.DeadCodex()
    analyzer.scan(
        "@route\n@router.get('/')\ndef endpoint():\n    pass\n",
        filename="module.py",
    )
    endpoint = analyzer.defined_funcs[0]
    assert endpoint.decorators == ("@route", "@router.get")


def test_decorator_adapter_normalizes_patterns():
    """Patterns without a leading '@' are normalized during construction."""
    adapter = DecoratorEntryPointAdapter(("job", "task.*"))
    assert adapter.patterns == ("@job", "@task.*")


def test_decorator_adapter_requires_patterns():
    """An adapter built without any pattern is rejected."""
    with pytest.raises(ValueError, match="decorator pattern"):
        DecoratorEntryPointAdapter(())


def test_flask_and_fastapi_adapters_only_discover_their_handlers():
    """Each framework adapter matches only its own routing decorators."""
    analyzer = core.DeadCodex()
    analyzer.scan(
        "@app.route('/')\n"
        "def flask_handler():\n"
        "    pass\n"
        "@router.websocket('/events')\n"
        "def socket_handler():\n"
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
    """The factory returns the adapter matching the configured name."""
    assert isinstance(make_framework_adapter("flask"), FlaskAdapter)
    assert isinstance(make_framework_adapter("fastapi"), FastAPIAdapter)
    with pytest.raises(ValueError, match="Unknown framework"):
        make_framework_adapter("django")

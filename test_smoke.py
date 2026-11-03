"""Smoke test: the package can be imported and reports a version."""

import deadcodex
from deadcodex.version import __version__


def test_package_importable():
    assert deadcodex is not None


def test_version_available():
    assert isinstance(__version__, str)
    assert __version__

"""Tests for the explicit command-line entry point."""

import pytest

from deadcodex import core
from deadcodex.utils import ExitCode
from deadcodex.version import __version__


def test_version_flag_prints_version_and_exits(monkeypatch, capsys):
    """`deadcodex --version` reports the version and exits successfully."""
    monkeypatch.setattr("sys.argv", ["deadcodex", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        core.main()
    captured = capsys.readouterr()
    assert exit_info.value.code == 0
    assert __version__ in captured.out


def test_help_flag_exits_without_scanning(monkeypatch, capsys):
    """`deadcodex --help` prints usage and exits successfully."""
    monkeypatch.setattr("sys.argv", ["deadcodex", "--help"])
    with pytest.raises(SystemExit) as exit_info:
        core.main()
    captured = capsys.readouterr()
    assert exit_info.value.code == 0
    assert "--framework" in captured.out


def test_missing_paths_reports_input_error(monkeypatch, capsys):
    """Running without any PATH exits with the config error exit code."""
    monkeypatch.setattr("sys.argv", ["deadcodex"])
    with pytest.raises(SystemExit) as exit_info:
        core.main()
    captured = capsys.readouterr()
    assert exit_info.value.code == ExitCode.InvalidCmdlineArguments
    assert "at least one file or directory" in captured.err


def test_unknown_framework_is_rejected(monkeypatch, capsys):
    """An unsupported --framework value is rejected by the parser."""
    monkeypatch.setattr("sys.argv", ["deadcodex", "--framework=django", "."])
    with pytest.raises(SystemExit) as exit_info:
        core.main()
    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert "django" in captured.err

"""Tests for the explicit command-line entry point."""

import pytest

from deadcodex import core
from deadcodex.utils import ExitCode
from deadcodex.version import __version__

from . import call_deadcodex


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


def test_scan_reports_findings_and_respects_confidence(tmp_path, capfd):
    path = tmp_path / "sample.py"
    path.write_text("def unused():\n    pass\n", encoding="utf-8")

    assert call_deadcodex([str(path)]) == ExitCode.DeadCode
    captured = capfd.readouterr()
    assert "sample.py:1: unused function 'unused'" in captured.out
    assert not captured.err
    assert call_deadcodex(["--min-confidence=100", str(path)]) == (
        ExitCode.NoDeadCode
    )
    assert not capfd.readouterr().out


def test_whitelist_can_be_written_to_a_file(tmp_path, capfd):
    path = tmp_path / "sample.py"
    path.write_text("def unused():\n    pass\n", encoding="utf-8")
    output = tmp_path / "whitelist.py"

    args = ["--make-whitelist", "--output", str(output), str(path)]
    assert call_deadcodex(args) == ExitCode.DeadCode
    assert output.read_text(encoding="utf-8").startswith(
        "unused  # unused function"
    )
    assert not capfd.readouterr().out


@pytest.mark.parametrize("option", ["--format=json", "--baseline=old.json"])
def test_pending_report_options_return_argument_error(tmp_path, capfd, option):
    path = tmp_path / "sample.py"
    path.write_text("", encoding="utf-8")

    assert (
        call_deadcodex([option, str(path)]) == ExitCode.InvalidCmdlineArguments
    )
    assert "available at this stage" in capfd.readouterr().err


@pytest.mark.parametrize(
    ("args", "decorator"),
    [
        (["--framework=flask"], "@app.route('/')"),
        (["--framework=fastapi"], "@router.get('/')"),
        (["--entry-point-decorator=job"], "@job"),
        (["--entry-point=sample.handler"], ""),
    ],
)
def test_project_entry_keeps_handler_and_its_callee(
    tmp_path, capfd, args, decorator
):
    path = tmp_path / "sample.py"
    path.write_text(
        "def helper():\n    pass\n"
        f"{decorator}\ndef handler():\n    helper()\n"
        "def unused():\n    pass\n",
        encoding="utf-8",
    )

    assert call_deadcodex([*args, str(path)]) == ExitCode.DeadCode
    captured = capfd.readouterr()
    assert "unused function 'unused'" in captured.out
    assert "unused function 'handler'" not in captured.out
    assert "unused function 'helper'" not in captured.out
    assert not captured.err


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("[tool.deadcodex\n", "Invalid TOML configuration"),
        ("[tool.deadcodex]\nframeworks = [42]\n", "list of strings"),
        ("[tool.deadcodex]\nmin_confidence = 101\n", "between 0 and 100"),
        (None, "Could not read configuration"),
    ],
)
def test_invalid_config_returns_argument_error(
    tmp_path, capfd, contents, message
):
    config = tmp_path / "settings.toml"
    if contents is not None:
        config.write_text(contents, encoding="utf-8")
    args = ["--config", str(config), str(tmp_path / "sample.py")]
    assert call_deadcodex(args) == ExitCode.InvalidCmdlineArguments
    error = capfd.readouterr().err
    assert message in error
    assert "Traceback" not in error


def test_cli_checks_confidence_before_scanning(tmp_path, capfd):
    args = ["--min-confidence=101", str(tmp_path / "missing.py")]
    assert call_deadcodex(args) == ExitCode.InvalidCmdlineArguments
    assert "between 0 and 100" in capfd.readouterr().err


def test_scan_error_takes_precedence_over_findings(tmp_path, capfd):
    (tmp_path / "broken.py").write_text("def :\n", encoding="utf-8")
    (tmp_path / "sample.py").write_text(
        "def unused():\n    pass\n", encoding="utf-8"
    )
    assert call_deadcodex([str(tmp_path)]) == ExitCode.InvalidInput
    captured = capfd.readouterr()
    assert "broken.py" in captured.err
    assert not captured.out

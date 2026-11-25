"""Tests for the explicit command-line entry point."""

import glob
import json
import os.path
import subprocess
import sys

import pytest

from deadcodex import core
from deadcodex.utils import ExitCode
from deadcodex.version import __version__

from . import REPO, WHITELISTS, call_deadcodex


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


def test_verbose_json_keeps_diagnostics_off_stdout(tmp_path, capfd):
    path = tmp_path / "sample.py"
    path.write_text("def unused():\n    pass\n", encoding="utf-8")
    config = tmp_path / "settings.toml"
    config.write_text("[tool.deadcodex]\nverbose = true\n", encoding="utf-8")

    args = ["--config", str(config), "--format=json", str(path)]
    assert call_deadcodex(args) == ExitCode.DeadCode
    captured = capfd.readouterr()
    assert json.loads(captured.out)["findings"][0]["name"] == "unused"
    assert "Reading configuration from" in captured.err
    assert "Scanning:" in captured.err


def test_cli_cannot_update_baseline_from_invalid_input(tmp_path, capfd):
    path = tmp_path / "broken.py"
    path.write_text("def :\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text("original", encoding="utf-8")
    args = [str(path), "--baseline", str(baseline), "--update-baseline"]

    assert call_deadcodex(args) == ExitCode.InvalidInput
    assert baseline.read_text(encoding="utf-8") == "original"
    assert "broken.py" in capfd.readouterr().err


def test_missing_baseline_returns_argument_error(tmp_path, capfd):
    path = tmp_path / "sample.py"
    path.write_text("", encoding="utf-8")
    assert (
        call_deadcodex(
            ["--baseline", str(tmp_path / "missing.json"), str(path)]
        )
        == ExitCode.InvalidCmdlineArguments
    )
    assert "Baseline file does not exist" in capfd.readouterr().err


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


def test_module_with_explicit_whitelists():
    assert call_deadcodex(["deadcodex/", *WHITELISTS]) == ExitCode.NoDeadCode


def test_module_with_implicit_whitelists():
    assert call_deadcodex(["deadcodex/"]) == ExitCode.NoDeadCode


def test_module_without_whitelists():
    assert (
        call_deadcodex(["deadcodex/", "--exclude", "whitelists"])
        == ExitCode.DeadCode
    )


def test_missing_file():
    assert call_deadcodex(["missing.py"]) == ExitCode.InvalidInput


def test_tests():
    assert call_deadcodex(["tests/"]) == ExitCode.NoDeadCode


def test_whitelists_with_python():
    for whitelist in WHITELISTS:
        assert (
            subprocess.call([sys.executable, whitelist], cwd=REPO)
            == ExitCode.NoDeadCode
        )


def test_pyc():
    assert call_deadcodex(["missing.pyc"]) == 1


def test_sort_by_size():
    assert (
        call_deadcodex(["deadcodex/utils.py", "--sort-by-size"])
        == ExitCode.DeadCode
    )


def test_min_confidence():
    assert (
        call_deadcodex(
            [
                "deadcodex/core.py",
                "--exclude",
                "whitelists",
                "--min-confidence",
                "100",
            ]
        )
        == ExitCode.NoDeadCode
    )


def test_exclude():
    def get_csv(paths):
        return ",".join(os.path.join("deadcodex", path) for path in paths)

    def call_deadcodex_with_excludes(excludes):
        return call_deadcodex(["deadcodex/", "--exclude", get_csv(excludes)])

    assert (
        call_deadcodex_with_excludes(["core.py", "utils.py"])
        == ExitCode.DeadCode
    )
    assert (
        call_deadcodex_with_excludes(glob.glob("deadcodex/*.py"))
        == ExitCode.NoDeadCode
    )


def test_make_whitelist():
    assert (
        call_deadcodex(
            ["deadcodex/", "--make-whitelist", "--exclude", "whitelists"]
        )
        == ExitCode.DeadCode
    )
    assert (
        call_deadcodex(["deadcodex/", "--make-whitelist"])
        == ExitCode.NoDeadCode
    )


def test_version():
    assert call_deadcodex(["--version"]) == ExitCode.NoDeadCode


def test_deadcodex_module_is_the_primary_cli():
    version_result = subprocess.run(
        [sys.executable, "-m", "deadcodex", "--version"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    help_result = subprocess.run(
        [sys.executable, "-m", "deadcodex", "--help"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert version_result.returncode == ExitCode.NoDeadCode
    assert version_result.stdout == f"deadcodex {__version__}\n"
    assert help_result.returncode == ExitCode.NoDeadCode
    assert help_result.stdout.startswith("usage: deadcodex ")


def test_project_aware_entry_point_distinguishes_same_named_functions(
    tmp_path,
):
    (tmp_path / "a.py").write_text("def run():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("def run():\n    pass\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "from a import run\nrun()\n", encoding="utf-8"
    )

    default_result = subprocess.run(
        [sys.executable, "-m", "deadcodex", str(tmp_path)],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    project_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadcodex",
            "--entry-point",
            "app",
            str(tmp_path),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert default_result.returncode == ExitCode.NoDeadCode
    assert default_result.stdout == ""
    assert project_result.returncode == ExitCode.DeadCode
    assert "b.py:1: unused function 'run'" in project_result.stdout


def test_project_aware_entry_point_reports_invalid_name(tmp_path):
    module = tmp_path / "module.py"
    module.write_text("def function():\n    pass\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadcodex",
            "--entry-point",
            "missing",
            str(module),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == ExitCode.InvalidCmdlineArguments
    assert "unresolved entry point: missing" in result.stderr


def test_project_aware_decorator_entry_point(tmp_path):
    module = tmp_path / "app.py"
    module.write_text(
        "def helper():\n"
        "    pass\n"
        "@router.get('/')\n"
        "def endpoint():\n"
        "    helper()\n"
        "def dead():\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadcodex",
            "--entry-point-decorator",
            "router.*",
            str(module),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == ExitCode.DeadCode
    assert "unused function 'dead'" in result.stdout
    assert "unused function 'endpoint'" not in result.stdout
    assert "unused function 'helper'" not in result.stdout


def test_fastapi_framework_entry_point(tmp_path):
    module = tmp_path / "app.py"
    module.write_text(
        "@router.get('/users')\n"
        "def users():\n"
        "    serialize()\n"
        "def serialize():\n"
        "    pass\n"
        "def obsolete():\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadcodex",
            "--framework",
            "fastapi",
            str(module),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == ExitCode.DeadCode
    assert "unused function 'obsolete'" in result.stdout
    assert "unused function 'users'" not in result.stdout
    assert "unused function 'serialize'" not in result.stdout

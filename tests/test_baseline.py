import json
import subprocess
import sys

import pytest

from deadcodex import core
from deadcodex.baseline import Baseline
from deadcodex.utils import ExitCode

from . import REPO


def _write(path, source):
    path.write_text(source, encoding="utf-8")


def _analyze(directory):
    analyzer = core.DeadCodex()
    analyzer.scavenge([directory])
    return analyzer


def test_updates_and_filters_baseline(tmp_path, capsys):
    module = tmp_path / "module.py"
    baseline_path = tmp_path / "baseline.json"
    _write(module, "def existing():\n    pass\n")
    analyzer = _analyze(tmp_path)

    exit_code = analyzer.report(baseline=baseline_path, update_baseline=True)

    assert exit_code is ExitCode.NoDeadCode
    assert capsys.readouterr().out == ""
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert payload["format"] == "deadcodex-baseline"
    assert payload["version"] == 1
    assert len(payload["entries"]) == 1

    _write(
        module,
        "\n\ndef existing():\n    pass\ndef newly_unused():\n    pass\n",
    )
    updated = _analyze(tmp_path)

    new_items = Baseline.load(baseline_path).filter(
        updated.get_unused_code(), updated.project.root
    )

    assert [item.name for item in new_items] == ["newly_unused"]


def test_report_with_baseline_only_emits_new_findings(tmp_path, capsys):
    module = tmp_path / "module.py"
    baseline_path = tmp_path / "baseline.json"
    _write(module, "def existing():\n    pass\n")
    _analyze(tmp_path).report(baseline=baseline_path, update_baseline=True)
    _write(
        module,
        "def existing():\n    pass\ndef newly_unused():\n    pass\n",
    )
    analyzer = _analyze(tmp_path)

    exit_code = analyzer.report(baseline=baseline_path)

    assert exit_code is ExitCode.DeadCode
    output = capsys.readouterr().out
    assert "newly_unused" in output
    assert "existing" not in output


def test_baseline_rejects_missing_and_invalid_files(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        Baseline.load(tmp_path / "missing.json")

    invalid = tmp_path / "invalid.json"
    _write(invalid, "not json")
    with pytest.raises(ValueError, match="Invalid baseline"):
        Baseline.load(invalid)

    unsupported = tmp_path / "unsupported.json"
    _write(
        unsupported,
        json.dumps(
            {"format": "deadcodex-baseline", "version": 2, "entries": []}
        ),
    )
    with pytest.raises(ValueError, match="Unsupported baseline version"):
        Baseline.load(unsupported)


def test_cli_baseline_workflow(tmp_path):
    module = tmp_path / "module.py"
    baseline_path = tmp_path / "baseline.json"
    _write(module, "def existing():\n    pass\n")

    update = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadcodex",
            str(module),
            "--baseline",
            str(baseline_path),
            "--update-baseline",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    filtered = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadcodex",
            str(module),
            "--baseline",
            str(baseline_path),
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert update.returncode == ExitCode.NoDeadCode
    assert baseline_path.is_file()
    assert filtered.returncode == ExitCode.NoDeadCode
    assert filtered.stdout == ""

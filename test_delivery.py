import json
import subprocess
import sys

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from deadcodex import DeadCodex, __version__
from deadcodex.utils import ExitCode

from . import REPO


def test_demo_project_end_to_end():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadcodex",
            "examples/demo_project",
            "--framework",
            "fastapi",
            "--format",
            "json",
        ],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == ExitCode.DeadCode
    payload = json.loads(result.stdout)
    function_names = {
        finding["name"]
        for finding in payload["findings"]
        if finding["kind"] == "function"
    }
    assert function_names == {"old_format_user"}


def test_ci_workflow_runs_lint_format_and_wheel_tests():
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert "ruff check deadcodex tests" in workflow
    assert "ruff format --check deadcodex tests" in workflow
    assert "tox -e py" in workflow


def test_package_exposes_deadcodex_command():
    with (REPO / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert pyproject["project"]["name"] == "deadcodex"
    assert pyproject["project"]["scripts"] == {
        "deadcodex": "deadcodex.core:main"
    }


def test_public_api_uses_deadcodex_name_and_version():
    assert DeadCodex.__name__ == "DeadCodex"
    assert __version__ == "1.0"

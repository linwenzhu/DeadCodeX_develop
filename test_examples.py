import json
import subprocess
import sys

from deadcodex.utils import ExitCode

from . import REPO


def _run_deadcodex(*args):
    return subprocess.run(
        [sys.executable, "-m", "deadcodex", *args],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )


def _json_function_names(result):
    assert result.returncode == ExitCode.DeadCode
    payload = json.loads(result.stdout)
    return {
        finding["qualified_name"] or finding["name"]
        for finding in payload["findings"]
        if finding["kind"] == "function"
    }


def test_basic_scan_example_covers_legacy_findings_and_noqa():
    result = _run_deadcodex("examples/01_basic_scan", "--format", "json")

    function_names = _json_function_names(result)
    payload = json.loads(result.stdout)
    all_names = {finding["name"] for finding in payload["findings"]}

    assert {
        "sample.unused_async_worker",
        "sample.unused_function",
    } <= function_names
    assert {"unused_method", "unused_property", "UnusedFormatter"} <= all_names
    assert "DOCUMENTATION_ONLY" not in all_names


def test_cross_file_example_resolves_reexports_aliases_and_same_names():
    result = _run_deadcodex(
        "examples/02_cross_file",
        "--entry-point",
        "app.main",
        "--format",
        "json",
    )

    assert _json_function_names(result) == {
        "shop.formatting.legacy_currency",
        "shop.legacy.checkout",
        "shop.taxes.obsolete_tax",
    }


def test_flask_example_discovers_route_entry_point():
    result = _run_deadcodex(
        "examples/03_flask_project",
        "--framework",
        "flask",
        "--format",
        "json",
    )

    assert _json_function_names(result) == {"app.obsolete_admin_panel"}


def test_custom_decorator_example_combines_entry_point_providers():
    result = _run_deadcodex(
        "examples/04_custom_decorator",
        "--entry-point",
        "jobs.job",
        "--entry-point-decorator",
        "job",
        "--format",
        "json",
    )

    assert _json_function_names(result) == {"jobs.old_cleanup"}


def test_configured_example_and_cli_override():
    result = _run_deadcodex(
        "--config",
        "examples/05_configured_project/pyproject.toml",
        "--format",
        "json",
    )

    assert _json_function_names(result) == {
        "app.deprecated_command",
        "helpers.legacy_calculation",
    }
    assert "generated_function" not in result.stdout
    assert "plugin_callback" not in result.stdout
    assert "ignored_by_name" not in result.stdout


def test_example_reports_and_baseline_workflow(tmp_path):
    html_report = tmp_path / "report.html"
    baseline = tmp_path / "baseline.json"

    html_result = _run_deadcodex(
        "examples/demo_project",
        "--framework",
        "fastapi",
        "--format",
        "html",
        "--output",
        str(html_report),
    )
    update_result = _run_deadcodex(
        "examples/demo_project",
        "--framework",
        "fastapi",
        "--baseline",
        str(baseline),
        "--update-baseline",
    )
    filtered_result = _run_deadcodex(
        "examples/demo_project",
        "--framework",
        "fastapi",
        "--baseline",
        str(baseline),
    )

    assert html_result.returncode == ExitCode.DeadCode
    assert "app.old_format_user" in html_report.read_text(encoding="utf-8")
    assert update_result.returncode == ExitCode.NoDeadCode
    assert baseline.is_file()
    assert filtered_result.returncode == ExitCode.NoDeadCode
    assert filtered_result.stdout == ""


def test_python_api_example_prints_edges_and_explanations():
    result = subprocess.run(
        [sys.executable, "examples/06_api_usage/analyze_project.py"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "app.main -> shop.service.checkout" in result.stdout
    assert "reachable via app.main" in result.stdout
    assert "shop.legacy.checkout" in result.stdout

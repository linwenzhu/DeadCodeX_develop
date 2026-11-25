import json

import pytest

from deadcodex import core
from deadcodex.utils import ExitCode


def test_json_report_contains_stable_finding_fields(capsys):
    analyzer = core.DeadCodex()
    analyzer.scan("def unused():\n    pass\n", filename="module.py")

    exit_code = analyzer.report(output_format="json")
    payload = json.loads(capsys.readouterr().out)

    assert exit_code is ExitCode.DeadCode
    assert payload["format"] == "deadcodex-findings"
    assert payload["version"] == 1
    assert payload["findings"] == [
        {
            "confidence": 60,
            "filename": "module.py",
            "first_lineno": 1,
            "kind": "function",
            "last_lineno": 2,
            "message": "unused function 'unused'",
            "name": "unused",
            "qualified_name": "module.unused",
            "size": 2,
        }
    ]


def test_json_report_represents_empty_result(capsys):
    analyzer = core.DeadCodex()
    analyzer.scan("value = 1\nprint(value)\n", filename="module.py")

    exit_code = analyzer.report(output_format="json")
    payload = json.loads(capsys.readouterr().out)

    assert exit_code is ExitCode.NoDeadCode
    assert payload["findings"] == []


def test_html_report_is_escaped_and_can_be_written(tmp_path, capsys):
    analyzer = core.DeadCodex()
    analyzer.scan("def dangerous_name():\n    pass\n", filename="<module>.py")
    output = tmp_path / "report.html"

    exit_code = analyzer.report(output_format="html", output=output)
    html = output.read_text(encoding="utf-8")

    assert exit_code is ExitCode.DeadCode
    assert capsys.readouterr().out == ""
    assert "<!doctype html>" in html
    assert "<title>DeadCodex findings</title>" in html
    assert "&lt;module&gt;.dangerous_name" in html
    assert "1 finding(s)" in html


def test_report_rejects_unknown_or_incompatible_format():
    analyzer = core.DeadCodex()
    analyzer.scan("def unused():\n    pass\n", filename="module.py")

    with pytest.raises(ValueError, match="Unknown output format"):
        analyzer.report(output_format="xml")
    with pytest.raises(ValueError, match="Whitelist output"):
        analyzer.report(make_whitelist=True, output_format="json")

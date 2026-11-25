import html
import json
from dataclasses import dataclass
from typing import Protocol

from deadcodex.model import Finding


class Reporter(Protocol):
    """Render a collection of findings into one output format."""

    def render(self, items) -> str:
        """Return a complete report string."""


@dataclass(frozen=True)
class ConsoleReporter:
    """Render findings with DeadCodex's traditional text syntax."""

    add_size: bool = False

    def render(self, items):
        lines = [item.get_report(add_size=self.add_size) for item in items]
        return _with_final_newline(lines)


class JsonReporter:
    """Render a stable, machine-readable JSON report."""

    def render(self, items):
        payload = {
            "format": "deadcodex-findings",
            "version": 1,
            "findings": [Finding.from_item(item).to_dict() for item in items],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


class HtmlReporter:
    """Render a standalone HTML report without external assets."""

    def render(self, items):
        findings = [Finding.from_item(item) for item in items]
        rows = "\n".join(self._row(finding) for finding in findings)
        empty_state = (
            ""
            if findings
            else '<p class="empty">No unused code was found.</p>'
        )
        table = (
            "<table><thead><tr><th>Location</th><th>Symbol</th>"
            "<th>Kind</th><th>Confidence</th><th>Message</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            if findings
            else ""
        )
        return (
            "<!doctype html>\n"
            '<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" '
            'content="width=device-width,initial-scale=1">'
            "<title>DeadCodex findings</title>"
            "<style>"
            "body{font-family:system-ui,sans-serif;margin:2rem;color:#202124}"
            "h1{font-size:1.6rem}p.summary{color:#5f6368}"
            "table{border-collapse:collapse;width:100%;font-size:.92rem}"
            "th,td{border:1px solid #dadce0;padding:.6rem;text-align:left}"
            "th{background:#174ea6;color:white}tbody tr:nth-child(even)"
            "{background:#f8fafd}.number{text-align:right;white-space:nowrap}"
            ".location{white-space:nowrap}.empty{color:#188038}"
            "</style></head><body><main><h1>DeadCodex findings</h1>"
            f'<p class="summary">{len(findings)} finding(s)</p>'
            f"{empty_state}{table}</main></body></html>\n"
        )

    @staticmethod
    def _row(finding):
        symbol = finding.qualified_name or finding.name
        location = f"{finding.filename}:{finding.first_lineno}"
        return (
            "<tr>"
            f'<td class="location">{html.escape(location)}</td>'
            f"<td>{html.escape(symbol)}</td>"
            f"<td>{html.escape(finding.kind)}</td>"
            f'<td class="number">{finding.confidence}%</td>'
            f"<td>{html.escape(finding.message)}</td>"
            "</tr>"
        )


def make_reporter(output_format, sort_by_size=False) -> Reporter:
    """Create a reporter for a validated output format name."""
    if output_format == "text":
        return ConsoleReporter(add_size=sort_by_size)
    if output_format == "json":
        return JsonReporter()
    if output_format == "html":
        return HtmlReporter()
    raise ValueError(f"Unknown output format: {output_format}")


def _with_final_newline(lines):
    return "\n".join(lines) + ("\n" if lines else "")

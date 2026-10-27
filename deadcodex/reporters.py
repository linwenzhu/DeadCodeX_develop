"""Human-readable and machine-readable reporting boundaries."""

from typing import Iterable, Protocol

from deadcodex.model import Finding


class Reporter(Protocol):
    def render(self, findings: Iterable[Finding]) -> str: ...


class ConsoleReporter:
    def render(self, findings: Iterable[Finding]) -> str:
        raise NotImplementedError


class JsonReporter:
    def render(self, findings: Iterable[Finding]) -> str:
        raise NotImplementedError


class HtmlReporter:
    def render(self, findings: Iterable[Finding]) -> str:
        raise NotImplementedError


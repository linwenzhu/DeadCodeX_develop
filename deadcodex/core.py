"""Public facade and command-line orchestration boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from deadcodex.model import Finding


class DeadCodex:
    def scan(self, source: str, filename: str | Path = "") -> None:
        raise NotImplementedError

    def scavenge(self, paths: Iterable[str | Path]) -> None:
        raise NotImplementedError

    def get_unused_code(self) -> list[Finding]:
        raise NotImplementedError

    def report(self) -> int:
        raise NotImplementedError


def main() -> None:
    """Run the DeadCodeX command-line application."""
    raise SystemExit(
        "DeadCodeX project framework initialized; implementation pending."
    )


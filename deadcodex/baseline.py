"""Known-finding baseline boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from deadcodex.model import Finding


class Baseline:
    @classmethod
    def load(cls, path: str | Path) -> "Baseline":
        raise NotImplementedError

    def filter(self, findings: Iterable[Finding]) -> list[Finding]:
        raise NotImplementedError

    def write(self, path: str | Path) -> None:
        raise NotImplementedError


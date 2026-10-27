"""Python source parsing boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deadcodex.model import ModuleModel


@dataclass
class ParsedModule:
    module: ModuleModel
    source: str
    tree: Any | None = None
    error: Exception | None = None


class PythonParser:
    def parse(
        self, source: str, filename: str | Path, module: ModuleModel
    ) -> ParsedModule:
        raise NotImplementedError


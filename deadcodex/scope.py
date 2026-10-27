"""Lexical scope collection boundary."""

from typing import Any

from deadcodex.model import ModuleModel


class ScopeCollector:
    def collect(self, module: ModuleModel, tree: Any) -> None:
        raise NotImplementedError


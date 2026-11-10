"""Project discovery and module loading boundary."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from deadcodex.model import ProjectModel


class ProjectLoader:
    def load(self, paths: Iterable[str | Path]) -> ProjectModel:
        raise NotImplementedError

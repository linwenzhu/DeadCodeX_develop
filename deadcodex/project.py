"""Project discovery and module loading boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from deadcodex.model import ProjectModel


class ProjectLoader:
    def load(self, paths: Iterable[str | Path]) -> ProjectModel:
        raise NotImplementedError


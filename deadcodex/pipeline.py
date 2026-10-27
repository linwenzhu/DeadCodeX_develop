"""Project analysis pipeline boundary."""

from typing import Protocol

from deadcodex.model import ProjectModel


class Analyzer(Protocol):
    def analyze(self, project: ProjectModel) -> object: ...


class ProjectAnalyzer:
    def analyze(self, project: ProjectModel) -> object:
        raise NotImplementedError


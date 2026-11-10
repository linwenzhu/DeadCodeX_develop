"""Definition and usage analysis boundary."""

from deadcodex.model import Finding, ProjectModel


class AnalysisResult:
    def get_unused_code(self) -> list[Finding]:
        raise NotImplementedError


class ProjectAnalysis:
    def analyze(self, project: ProjectModel) -> list[Finding]:
        raise NotImplementedError


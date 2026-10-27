"""Cross-file import and reference resolution boundaries."""

from deadcodex.model import ProjectModel


class ImportResolver:
    def resolve(self, project: ProjectModel) -> None:
        raise NotImplementedError


class ReferenceResolver:
    def resolve(self, project: ProjectModel) -> None:
        raise NotImplementedError


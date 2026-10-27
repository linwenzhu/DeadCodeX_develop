"""Framework entry-point discovery boundaries."""

from typing import Protocol

from deadcodex.model import ProjectModel, QualifiedName


class EntryPointProvider(Protocol):
    def discover(self, project: ProjectModel) -> frozenset[QualifiedName]: ...


class FlaskAdapter:
    def discover(self, project: ProjectModel) -> frozenset[QualifiedName]:
        raise NotImplementedError


class FastAPIAdapter:
    def discover(self, project: ProjectModel) -> frozenset[QualifiedName]:
        raise NotImplementedError


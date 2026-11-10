"""Domain models shared by all analysis stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


@dataclass(frozen=True, order=True)
class QualifiedName:
    parts: tuple[str, ...]

    def __str__(self) -> str:
        return ".".join(self.parts)


class ResolutionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    EXTERNAL = "external"


@dataclass
class Scope:
    qualified_name: QualifiedName
    kind: str
    parent: "Scope | None" = None


@dataclass
class ModuleModel:
    path: Path
    qualified_name: QualifiedName
    scopes: list[Scope] = field(default_factory=list)
    imports: list[object] = field(default_factory=list)
    references: list[object] = field(default_factory=list)
    calls: list[object] = field(default_factory=list)


@dataclass
class ProjectModel:
    root: Path
    modules: list[ModuleModel] = field(default_factory=list)


@dataclass(frozen=True)
class Finding:
    filename: Path
    line: int
    kind: str
    name: str
    confidence: int


import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from deadcodex import utils

DEFAULT_CONFIDENCE = 60


@dataclass(frozen=True, order=True)
class QualifiedName:
    """A stable, dotted identity for modules and nested definitions."""

    parts: tuple[str, ...]

    def __post_init__(self):
        if not self.parts or any(not part for part in self.parts):
            raise ValueError("A qualified name must contain non-empty parts.")

    @classmethod
    def from_string(cls, value):
        return cls(tuple(value.split(".")))

    @property
    def name(self):
        return self.parts[-1]

    @property
    def parent(self):
        if len(self.parts) == 1:
            return None
        return QualifiedName(self.parts[:-1])

    def child(self, name):
        if not name or "." in name:
            raise ValueError("A child name must be one non-empty name part.")
        return QualifiedName((*self.parts, name))

    def __str__(self):
        return ".".join(self.parts)


class ScopeKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"


class ImportKind(str, Enum):
    MODULE = "module"
    SYMBOL = "symbol"


class UsageKind(str, Enum):
    NAME = "name"
    ATTRIBUTE = "attribute"


class ResolutionStatus(str, Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass
class ImportBinding:
    """One imported local name and its optional project-level target."""

    kind: ImportKind
    bound_name: str
    module_name: Optional[str]
    imported_name: Optional[str]
    level: int
    first_lineno: int
    alias: Optional[str] = None
    status: ResolutionStatus = ResolutionStatus.PENDING
    target: Optional[QualifiedName] = None
    scope_name: Optional[QualifiedName] = None


@dataclass
class UsageReference:
    """A name or attribute read and its optional qualified target."""

    kind: UsageKind
    name: str
    parts: tuple[str, ...]
    scope_name: QualifiedName
    filename: Path
    first_lineno: int
    status: ResolutionStatus = ResolutionStatus.PENDING
    target: Optional[QualifiedName] = None
    binding_target: Optional[QualifiedName] = None


@dataclass
class CallSite:
    """A call expression and its optional statically resolved target."""

    caller: QualifiedName
    callee_parts: tuple[str, ...]
    filename: Path
    first_lineno: int
    status: ResolutionStatus = ResolutionStatus.PENDING
    target: Optional[QualifiedName] = None


@dataclass(eq=False)
class Scope:
    """A lexical scope in a module's definition hierarchy."""

    qualified_name: QualifiedName
    kind: ScopeKind
    parent: Optional["Scope"] = None
    first_lineno: int = 1
    last_lineno: Optional[int] = None
    children: list["Scope"] = field(default_factory=list)

    @property
    def name(self):
        return self.qualified_name.name

    def add_child(
        self, name, kind, first_lineno=1, last_lineno=None
    ) -> "Scope":
        child = Scope(
            qualified_name=self.qualified_name.child(name),
            kind=kind,
            parent=self,
            first_lineno=first_lineno,
            last_lineno=last_lineno,
        )
        self.children.append(child)
        return child


@dataclass
class ModuleModel:
    """Project-level identity and scope information for one source module."""

    path: Path
    qualified_name: QualifiedName
    source_root: Path
    is_package: bool = False
    scope: Scope = field(init=False)
    scope_by_node_id: dict[int, Scope] = field(default_factory=dict)
    imports: list[ImportBinding] = field(default_factory=list)
    references: list[UsageReference] = field(default_factory=list)
    calls: list[CallSite] = field(default_factory=list)

    def __post_init__(self):
        self.is_package = self.is_package or self.path.name == "__init__.py"
        self.scope = Scope(self.qualified_name, ScopeKind.MODULE)

    @property
    def name(self):
        return str(self.qualified_name)

    def scope_for_node(self, node):
        return self.scope_by_node_id.get(id(node), self.scope)

    def scope_named(self, qualified_name):
        target = str(qualified_name)
        pending = [self.scope]
        while pending:
            scope = pending.pop()
            if str(scope.qualified_name) == target:
                return scope
            pending.extend(scope.children)
        return None

    def reset_analysis(self):
        self.scope.children.clear()
        self.scope_by_node_id.clear()
        self.imports.clear()
        self.references.clear()
        self.calls.clear()


@dataclass
class ProjectModel:
    """An ordered collection of modules discovered for one analysis run."""

    root: Path
    modules: list[ModuleModel] = field(default_factory=list)

    def __post_init__(self):
        self.root = Path(self.root)

    def add_module(self, module):
        self.modules.append(module)
        return module

    def include(self, project):
        if self.modules and project.modules:
            self.root = Path(os.path.commonpath([self.root, project.root]))
        elif project.modules:
            self.root = project.root
        self.modules.extend(project.modules)
        return project.modules

    def module_for_path(self, path):
        target = Path(path).resolve()
        return next(
            (
                module
                for module in self.modules
                if module.path.resolve() == target
            ),
            None,
        )

    def modules_named(self, qualified_name):
        name = str(qualified_name)
        return [module for module in self.modules if module.name == name]


class Item:
    """Hold the name, type and location of defined code."""

    __slots__ = (
        "confidence",
        "decorators",
        "filename",
        "first_lineno",
        "last_lineno",
        "message",
        "name",
        "qualified_name",
        "typ",
    )

    def __init__(
        self,
        name,
        typ,
        filename,
        first_lineno,
        last_lineno,
        message="",
        confidence=DEFAULT_CONFIDENCE,
        qualified_name=None,
        decorators=(),
    ):
        self.name: str = name
        self.typ: str = typ
        self.filename: Path = filename
        self.first_lineno: int = first_lineno
        self.last_lineno: int = last_lineno
        self.message: str = message or f"unused {typ} '{name}'"
        self.confidence: int = confidence
        self.qualified_name: Optional[QualifiedName] = qualified_name
        self.decorators: tuple[str, ...] = tuple(decorators)

    @property
    def size(self):
        assert self.last_lineno >= self.first_lineno
        return self.last_lineno - self.first_lineno + 1

    def get_report(self, add_size=False):
        if add_size:
            line_format = "line" if self.size == 1 else "lines"
            size_report = f", {self.size:d} {line_format}"
        else:
            size_report = ""
        return (
            f"{utils.format_path(self.filename)}:{self.first_lineno:d}: "
            f"{self.message} ({self.confidence}% confidence{size_report})"
        )

    def get_whitelist_string(self):
        filename = utils.format_path(self.filename)
        if self.typ == "unreachable_code":
            return f"# {self.message} ({filename}:{self.first_lineno})"
        prefix = ""
        if self.typ in ["attribute", "method", "property"]:
            prefix = "_."
        return (
            f"{prefix}{self.name}  # unused {self.typ} "
            f"({filename}:{self.first_lineno:d})"
        )

    def _tuple(self):
        return self.filename, self.first_lineno, self.name

    def __repr__(self):
        return repr(self.name)

    def __eq__(self, other):
        return self._tuple() == other._tuple()

    def __hash__(self):
        return hash(self._tuple())


@dataclass(frozen=True)
class Finding:
    """Stable, reporter-facing representation of an unused-code item."""

    name: str
    kind: str
    filename: str
    first_lineno: int
    last_lineno: int
    message: str
    confidence: int
    size: int
    qualified_name: Optional[str] = None

    @classmethod
    def from_item(cls, item):
        return cls(
            name=item.name,
            kind=item.typ,
            filename=str(utils.format_path(item.filename)),
            first_lineno=item.first_lineno,
            last_lineno=item.last_lineno,
            message=item.message,
            confidence=item.confidence,
            size=item.size,
            qualified_name=(
                str(item.qualified_name)
                if item.qualified_name is not None
                else None
            ),
        )

    def to_dict(self):
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "filename": self.filename,
            "first_lineno": self.first_lineno,
            "last_lineno": self.last_lineno,
            "size": self.size,
            "message": self.message,
            "confidence": self.confidence,
        }

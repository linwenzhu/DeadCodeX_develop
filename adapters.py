from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Protocol

from deadcodex.callgraph import CALLABLE_TYPES
from deadcodex.model import QualifiedName


class EntryPointProvider(Protocol):
    """Extension interface for discovering implicit project entry points."""

    def discover(self, project, defined_items) -> frozenset[QualifiedName]:
        """Return qualified entry points found in an analyzed project."""


class FrameworkAdapter(EntryPointProvider, Protocol):
    """Entry-point provider associated with one supported framework."""

    framework: str


@dataclass(frozen=True)
class DecoratorEntryPointAdapter:
    """Discover callables whose decorators match configured glob patterns."""

    patterns: tuple[str, ...]

    def __post_init__(self):
        if not self.patterns:
            raise ValueError("At least one decorator pattern is required.")
        normalized = tuple(
            pattern if pattern.startswith("@") else f"@{pattern}"
            for pattern in self.patterns
        )
        object.__setattr__(self, "patterns", normalized)

    def discover(self, project, defined_items):
        project_paths = {module.path.resolve() for module in project.modules}
        return frozenset(
            item.qualified_name
            for item in defined_items
            if item.typ in CALLABLE_TYPES
            and item.qualified_name is not None
            and item.filename.resolve() in project_paths
            and any(
                fnmatchcase(decorator, pattern)
                for decorator in item.decorators
                for pattern in self.patterns
            )
        )


class FlaskAdapter(DecoratorEntryPointAdapter):
    """Discover Flask application and blueprint route handlers."""

    framework = "flask"

    def __init__(self):
        super().__init__(
            (
                "*.route",
                "*.get",
                "*.post",
                "*.put",
                "*.patch",
                "*.delete",
                "*.options",
                "*.head",
            )
        )


class FastAPIAdapter(DecoratorEntryPointAdapter):
    """Discover FastAPI application and router operation handlers."""

    framework = "fastapi"

    def __init__(self):
        super().__init__(
            (
                "*.api_route",
                "*.websocket",
                "*.websocket_route",
                "*.get",
                "*.post",
                "*.put",
                "*.patch",
                "*.delete",
                "*.options",
                "*.head",
            )
        )


def make_framework_adapter(name) -> FrameworkAdapter:
    """Create a supported framework adapter by configuration name."""
    if name == FlaskAdapter.framework:
        return FlaskAdapter()
    if name == FastAPIAdapter.framework:
        return FastAPIAdapter()
    raise ValueError(f"Unknown framework adapter: {name}")

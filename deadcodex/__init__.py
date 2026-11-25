"""Public package interface for DeadCodeX."""

from deadcodex.adapters import (
    DecoratorEntryPointAdapter,
    EntryPointProvider,
    FastAPIAdapter,
    FlaskAdapter,
    FrameworkAdapter,
)
from deadcodex.core import DeadCodex
from deadcodex.pipeline import Analyzer, PipelineResult, ProjectAnalyzer
from deadcodex.version import __version__

__all__ = [
    "Analyzer",
    "DeadCodex",
    "DecoratorEntryPointAdapter",
    "EntryPointProvider",
    "FastAPIAdapter",
    "FlaskAdapter",
    "FrameworkAdapter",
    "PipelineResult",
    "ProjectAnalyzer",
    "__version__",
]

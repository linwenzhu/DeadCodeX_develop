"""Public package interface for DeadCodeX."""

from deadcodex.core import DeadCodex
from deadcodex.pipeline import PipelineResult, ProjectAnalyzer
from deadcodex.version import __version__

__all__ = ["DeadCodex", "PipelineResult", "ProjectAnalyzer", "__version__"]

"""Run project analysis stages in dependency order."""

from dataclasses import dataclass
from typing import Optional, Protocol

from deadcodex.callgraph import CallGraphBuilder, ReachabilityAnalyzer
from deadcodex.model import CallGraph, ProjectModel, ReachabilityResult
from deadcodex.resolver import ImportResolver, ReferenceResolver


@dataclass
class PipelineResult:
    """The graph and optional explicit-entry reachability for one run."""

    call_graph: CallGraph
    reachability: Optional[ReachabilityResult] = None


class Analyzer(Protocol):
    def analyze(
        self, project: ProjectModel, defined_items=(), entry_points=()
    ) -> PipelineResult: ...


class ProjectAnalyzer:
    """Resolve imports, references, calls, then optional reachability.

    Pass definitions collected for the project. Empty entry points request
    reference analysis only. Each run rebuilds results from current facts.
    """

    def __init__(self, call_graph_builder=None, reachability_analyzer=None):
        self.call_graph_builder = (
            call_graph_builder
            if call_graph_builder is not None
            else CallGraphBuilder()
        )
        self.reachability_analyzer = (
            reachability_analyzer
            if reachability_analyzer is not None
            else ReachabilityAnalyzer()
        )

    def analyze(
        self, project: ProjectModel, defined_items=(), entry_points=()
    ) -> PipelineResult:
        items = tuple(defined_items)
        entries = tuple(entry_points)
        definitions = tuple(item for item in items if item.typ != "import")
        ImportResolver(definitions).resolve(project)
        ReferenceResolver(definitions).resolve(project)
        graph = self.call_graph_builder.build(project, items)
        reachability = (
            self.reachability_analyzer.analyze(project, items, graph, entries)
            if entries
            else None
        )
        return PipelineResult(graph, reachability)

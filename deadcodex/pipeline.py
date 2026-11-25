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

    def __init__(
        self,
        call_graph_builder=None,
        reachability_analyzer=None,
        legacy_call_graph_builder=None,
        *,
        import_resolver=None,
        reference_resolver=None,
    ):
        # The original API accepts three analysis passes and returns the graph.
        self._return_graph = legacy_call_graph_builder is not None or (
            import_resolver is not None
            and reference_resolver is not None
            and reachability_analyzer is None
        )
        if legacy_call_graph_builder is not None:
            import_resolver = call_graph_builder
            reference_resolver = reachability_analyzer
            call_graph_builder = legacy_call_graph_builder
            reachability_analyzer = None
        self.import_resolver = (
            ImportResolver() if import_resolver is None else import_resolver
        )
        self.reference_resolver = (
            ReferenceResolver()
            if reference_resolver is None
            else reference_resolver
        )
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
        self,
        project: ProjectModel,
        defined_items=(),
        entry_points=(),
        *,
        imports_resolved=False,
    ):
        if self._return_graph and isinstance(entry_points, bool):
            imports_resolved = entry_points
        items = defined_items if self._return_graph else tuple(defined_items)
        if not imports_resolved:
            self.import_resolver.resolve(project, items)
        self.reference_resolver.resolve(project, items)
        graph = self.call_graph_builder.build(project, items)
        if self._return_graph:
            return graph
        entries = tuple(entry_points)
        reachability = (
            self.reachability_analyzer.analyze(project, items, graph, entries)
            if entries
            else None
        )
        return PipelineResult(graph, reachability)

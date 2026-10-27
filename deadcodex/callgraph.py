"""Project call graph and reachability boundaries."""

from dataclasses import dataclass, field

from deadcodex.model import ProjectModel, QualifiedName


@dataclass
class CallGraph:
    edges: dict[QualifiedName, set[QualifiedName]] = field(default_factory=dict)


class CallGraphBuilder:
    def build(self, project: ProjectModel) -> CallGraph:
        raise NotImplementedError


class ReachabilityAnalyzer:
    def analyze(
        self, graph: CallGraph, entry_points: set[QualifiedName]
    ) -> set[QualifiedName]:
        raise NotImplementedError


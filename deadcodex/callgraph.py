from collections import Counter, defaultdict, deque

from deadcodex.model import (
    CallEdge,
    CallGraph,
    QualifiedName,
    ReachabilityResult,
    ResolutionStatus,
)

CALLABLE_TYPES = frozenset({"class", "function", "method"})


class CallGraphBuilder:
    """Build resolved call edges from collected and resolved references."""

    def build(self, project, defined_items):
        callable_targets = {
            item.qualified_name
            for item in defined_items
            if item.typ in CALLABLE_TYPES and item.qualified_name is not None
        }
        reference_index = defaultdict(list)
        for module in project.modules:
            for reference in module.references:
                key = (
                    reference.scope_name,
                    reference.parts,
                    reference.filename.resolve(),
                    reference.first_lineno,
                )
                reference_index[key].append(reference)

        graph = CallGraph()
        self.status_counts = Counter()
        for module in project.modules:
            graph.calls.extend(module.calls)
            for call in module.calls:
                self._resolve_call(
                    call, reference_index, callable_targets, graph
                )
                self.status_counts[call.status] += 1
        graph.edges.sort(
            key=lambda edge: (
                str(edge.caller),
                str(edge.callee),
                str(edge.filename),
                edge.first_lineno,
            )
        )
        return graph

    @staticmethod
    def _resolve_call(call, reference_index, callable_targets, graph):
        if not call.callee_parts:
            call.status = ResolutionStatus.UNRESOLVED
            call.target = None
            return

        key = (
            call.caller,
            call.callee_parts,
            call.filename.resolve(),
            call.first_lineno,
        )
        references = reference_index[key]
        outcomes = {
            (reference.status, reference.target) for reference in references
        }
        if len(outcomes) != 1:
            call.status = (
                ResolutionStatus.AMBIGUOUS
                if outcomes
                else ResolutionStatus.UNRESOLVED
            )
            call.target = None
            return

        status, target = outcomes.pop()
        call.status = status
        call.target = target
        if status is not ResolutionStatus.RESOLVED:
            return
        if target not in callable_targets:
            call.status = ResolutionStatus.UNRESOLVED
            call.target = None
            return
        graph.edges.append(
            CallEdge(
                caller=call.caller,
                callee=target,
                filename=call.filename,
                first_lineno=call.first_lineno,
            )
        )


class ReachabilityAnalyzer:
    """Traverse a call graph from explicit, unambiguous entry points."""

    def analyze(self, project, defined_items, graph, entry_points):
        requested = tuple(
            self._as_qualified_name(name) for name in entry_points
        )
        if not requested:
            raise ValueError("At least one entry point is required.")

        target_counts = Counter(
            module.qualified_name for module in project.modules
        )
        callable_targets = {
            item.qualified_name
            for item in defined_items
            if item.typ in CALLABLE_TYPES and item.qualified_name is not None
        }
        target_counts.update(
            item.qualified_name
            for item in defined_items
            if item.typ in CALLABLE_TYPES and item.qualified_name is not None
        )

        resolved = {
            target for target in requested if target_counts[target] == 1
        }
        unresolved = {
            target for target in requested if target_counts[target] == 0
        }
        ambiguous = {
            target for target in requested if target_counts[target] > 1
        }

        adjacency = defaultdict(set)
        for edge in graph.edges:
            adjacency[edge.caller].add(edge.callee)

        predecessors = dict.fromkeys(resolved)
        pending = deque(sorted(resolved))
        while pending:
            caller = pending.popleft()
            for callee in sorted(adjacency[caller]):
                if callee not in predecessors:
                    predecessors[callee] = caller
                    pending.append(callee)

        reachable = frozenset(predecessors)
        result = ReachabilityResult(
            entry_points=frozenset(resolved),
            reachable=reachable,
            unreachable=frozenset(callable_targets - reachable),
            unresolved_entry_points=frozenset(unresolved),
            ambiguous_entry_points=frozenset(ambiguous),
            predecessors=predecessors,
        )
        self.status_counts = Counter(
            {
                ResolutionStatus.RESOLVED: len(result.entry_points),
                ResolutionStatus.UNRESOLVED: len(
                    result.unresolved_entry_points
                ),
                ResolutionStatus.AMBIGUOUS: len(result.ambiguous_entry_points),
            }
        )
        return result

    @staticmethod
    def _as_qualified_name(name):
        return (
            name
            if isinstance(name, QualifiedName)
            else QualifiedName.from_string(name)
        )

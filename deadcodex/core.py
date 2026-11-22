"""Public facade for the stage-A parser and collector workflow."""

import pkgutil
import sys
from collections import defaultdict
from pathlib import Path

from deadcodex import utils
from deadcodex.adapters import (
    DecoratorEntryPointAdapter,
    make_framework_adapter,
)
from deadcodex.analysis import ProjectAnalysis
from deadcodex.callgraph import (
    CALLABLE_TYPES,
    CallGraphBuilder,
    ReachabilityAnalyzer,
)
from deadcodex.collector import AstCollector, _match
from deadcodex.config import InputError, make_config
from deadcodex.model import CallGraph, ProjectModel, ResolutionStatus
from deadcodex.parser import PythonParser
from deadcodex.pipeline import ProjectAnalyzer
from deadcodex.project import ProjectLoader
from deadcodex.resolver import ImportResolver, ReferenceResolver
from deadcodex.scope import ScopeCollector
from deadcodex.utils import ExitCode


class DeadCodex(AstCollector):
    """Parse source files and collect module-local analysis facts."""

    def __init__(
        self, verbose=False, ignore_names=None, ignore_decorators=None
    ):
        super().__init__(
            verbose=verbose,
            ignore_names=ignore_names,
            ignore_decorators=ignore_decorators,
        )
        self.parser = PythonParser()
        self.project_loader = ProjectLoader()
        self.scope_collector = ScopeCollector()
        self.project = ProjectModel(root=Path())
        self.exit_code = ExitCode.NoDeadCode
        self.call_graph_builder = CallGraphBuilder()
        self.project_reachability_analyzer = ReachabilityAnalyzer()
        self.call_graph = CallGraph()
        self.project_reachability = None

    def scan(self, code, filename="", module=None):
        """Parse one source string and collect its AST facts."""

        if module is None:
            module = (
                self.project.module_for_path(filename) if filename else None
            )
            if module is None:
                module = (
                    self.project_loader.module_from_path(filename)
                    if filename
                    else self.project_loader.in_memory_module()
                )
                self.project.add_module(module)
        else:
            filename = module.path

        module.reset_analysis()
        parsed_module = self.parser.parse(
            code, filename=filename, module=module
        )
        self.prepare_module(parsed_module)

        if isinstance(parsed_module.error, SyntaxError):
            self._handle_syntax_error(parsed_module.error)
            self.reachability.reset()
        elif isinstance(parsed_module.error, ValueError):
            message = (
                f"{utils.format_path(parsed_module.filename)}: "
                f'invalid source code "{parsed_module.error}"'
            )
            self._log(message, file=sys.stderr, force=True)
            self.exit_code = ExitCode.InvalidInput
            self.reachability.reset()
        else:
            self.scope_collector.collect(module, parsed_module.tree)
            try:
                self.collect(parsed_module)
            except SyntaxError as error:
                # Parsing a malformed type comment can fail during collection.
                self._handle_syntax_error(error)

    def _handle_syntax_error(self, error):
        text = f' at "{error.text.strip()}"' if error.text else ""
        self._log(
            f"{utils.format_path(self.filename)}:{error.lineno}: "
            f"{error.msg}{text}",
            file=sys.stderr,
            force=True,
        )
        self.exit_code = ExitCode.InvalidInput

    def scavenge(self, paths, exclude=None):
        """Discover Python files, scan them, and include known whitelists."""

        def prepare_pattern(pattern):
            if not any(char in pattern for char in "*?["):
                pattern = f"*{pattern}*"
            return pattern

        exclude = [prepare_pattern(pattern) for pattern in (exclude or [])]

        def exclude_path(path):
            return _match(path, exclude, case=False)

        discovered_project = self.project_loader.load(paths)
        discovered_modules = self.project.include(discovered_project)

        for module in discovered_modules:
            if exclude_path(module.path):
                self._log("Excluded:", module.path)
                continue

            self._log("Scanning:", module.path)
            try:
                module_string = self.project_loader.read_module(module)
            except utils.DeadCodexInputException as error:
                self._log(
                    f"Error: Could not read file {module.path} - {error}\n"
                    "Try to change the encoding to UTF-8.",
                    file=sys.stderr,
                    force=True,
                )
                self.exit_code = ExitCode.InvalidInput
            else:
                self.scan(module_string, module=module)

        unique_imports = {item.name for item in self.defined_imports}
        for import_name in unique_imports:
            path = Path("whitelists") / f"{import_name}_whitelist.py"
            if exclude_path(path):
                self._log("Excluded whitelist:", path)
                continue
            try:
                module_data = pkgutil.get_data("deadcodex", str(path))
            except OSError:
                continue
            if module_data is None:
                continue
            self._log("Included whitelist:", path)
            self.scan(module_data.decode("utf-8"), filename=path)

    def resolve_imports(self):
        """Resolve collected imports against modules in the project."""

        definitions = (
            self.defined_attrs
            + self.defined_classes
            + self.defined_funcs
            + self.defined_methods
            + self.defined_props
            + self.defined_vars
        )
        ImportResolver(definitions).resolve(self.project)

    def resolve_references(self):
        """Resolve collected references after import resolution."""

        definitions = (
            self.defined_attrs
            + self.defined_classes
            + self.defined_funcs
            + self.defined_methods
            + self.defined_props
            + self.defined_vars
        )
        self.resolve_imports()
        ReferenceResolver(definitions).resolve(self.project)
        self.call_graph = self.call_graph_builder.build(
            self.project, self.defined_items
        )
        return self.call_graph

    def analyze_reachability(self, entry_points=()):
        """Traverse known call edges from explicit qualified entry points."""
        entries = tuple(entry_points)
        if not entries:
            raise ValueError("At least one entry point is required.")
        return self.run_pipeline(entries).reachability

    def run_pipeline(self, entry_points=()):
        """Run ordered analysis on all currently collected project facts."""
        pipeline = ProjectAnalyzer(
            self.call_graph_builder, self.project_reachability_analyzer
        )
        result = pipeline.analyze(
            self.project, self.defined_items, entry_points
        )
        self.call_graph = result.call_graph
        self.project_reachability = result.reachability
        return result

    def get_unused_code(
        self, min_confidence=0, sort_by_size=False, *, qualified=False
    ):
        """Use legacy name matching unless qualified analysis is requested."""
        if not qualified:
            return super().get_unused_code(min_confidence, sort_by_size)
        if not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be between 0 and 100.")
        self.run_pipeline()
        return ProjectAnalysis().analyze(
            self.project, self, min_confidence, sort_by_size
        )

    def get_unused_code_project(
        self, entry_points=(), min_confidence=0, sort_by_size=False
    ):
        """Report experimental project-level unreachable callables."""
        if not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be between 0 and 100.")
        result = self.analyze_reachability(entry_points)
        invalid = (
            result.unresolved_entry_points | result.ambiguous_entry_points
        )
        if invalid:
            explanations = "; ".join(
                result.explain(target) for target in sorted(invalid)
            )
            raise ValueError(
                f"Invalid or ambiguous entry points: {explanations}"
            )

        uncertain_names = {
            call.callee_parts[-1]
            for call in self.call_graph.calls
            if call.callee_parts
            and call.status
            in {ResolutionStatus.UNRESOLVED, ResolutionStatus.AMBIGUOUS}
        }
        # Unknown calls may reach same-named callables and their callees.
        protected = {
            item.qualified_name
            for item in self.defined_items
            if item.typ in CALLABLE_TYPES and item.name in uncertain_names
        }
        adjacency = defaultdict(set)
        for edge in self.call_graph.edges:
            adjacency[edge.caller].add(edge.callee)
        pending = list(protected)
        while pending:
            for callee in adjacency[pending.pop()]:
                if callee not in protected:
                    protected.add(callee)
                    pending.append(callee)

        items = {
            item
            for item in self.defined_items
            if item.typ in CALLABLE_TYPES
            and item.qualified_name in result.unreachable - protected
        }
        # Reuse references already resolved by analyze_reachability.
        items.update(
            item
            for item in ProjectAnalysis().analyze(self.project, self)
            if item.typ not in CALLABLE_TYPES
        )
        findings = [
            item for item in items if item.confidence >= min_confidence
        ]

        def sort_key(item):
            location = (str(item.filename).lower(), item.first_lineno)
            return (item.size, *location) if sort_by_size else location

        return sorted(findings, key=sort_key)

    def report(self):
        """Reporting is connected during F's second submission."""

        raise NotImplementedError


def main():
    try:
        config = make_config()
    except InputError as error:
        print(error, file=sys.stderr)
        sys.exit(ExitCode.InvalidCmdlineArguments)

    deadcodex = DeadCodex(
        verbose=config["verbose"],
        ignore_names=config["ignore_names"],
        ignore_decorators=config["ignore_decorators"],
    )
    deadcodex.scavenge(config["paths"], exclude=config["exclude"])
    entry_point_providers = [
        make_framework_adapter(name) for name in config["frameworks"]
    ]
    if config["entry_point_decorators"]:
        entry_point_providers.append(
            DecoratorEntryPointAdapter(tuple(config["entry_point_decorators"]))
        )
    try:
        exit_code = deadcodex.report(
            min_confidence=config["min_confidence"],
            sort_by_size=config["sort_by_size"],
            make_whitelist=config["make_whitelist"],
            entry_points=config["entry_points"],
            entry_point_providers=tuple(entry_point_providers),
            output_format=config["output_format"],
            output=config["output"],
            baseline=config["baseline"],
            update_baseline=config["update_baseline"],
        )
    except ValueError as error:
        print(error, file=sys.stderr)
        sys.exit(ExitCode.InvalidCmdlineArguments)
    sys.exit(exit_code)

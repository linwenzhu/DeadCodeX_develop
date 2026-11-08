"""Public facade for the stage-A parser and collector workflow."""

import pkgutil
import sys
from pathlib import Path

from deadcodex import utils
from deadcodex.collector import AstCollector, _match
from deadcodex.model import ProjectModel
from deadcodex.parser import PythonParser
from deadcodex.project import ProjectLoader
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

    def report(self):
        """Reporting is connected during F's second submission."""

        raise NotImplementedError


def main():
    """The CLI is connected during E's submission."""

    raise SystemExit(
        "DeadCodeX parser and collector are ready; CLI integration pending."
    )

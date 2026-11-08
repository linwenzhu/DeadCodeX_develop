import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from deadcodex import noqa
from deadcodex.model import ModuleModel


@dataclass(frozen=True)
class ParsedModule:
    """A source module and the result of parsing it."""

    filename: Path
    source_lines: list[str]
    noqa_lines: dict
    module: Optional[ModuleModel] = None
    tree: Optional[ast.Module] = None
    error: Optional[Union[SyntaxError, ValueError]] = None


class PythonParser:
    """Convert Python source into an AST plus collection metadata."""

    def parse(self, code, filename="", module=None):
        filename = Path(filename)
        source_lines = code.splitlines()
        noqa_lines = noqa.parse_noqa(source_lines)

        try:
            tree = ast.parse(code, filename=str(filename), type_comments=True)
        except (SyntaxError, ValueError) as error:
            return ParsedModule(
                filename=filename,
                source_lines=source_lines,
                noqa_lines=noqa_lines,
                module=module,
                error=error,
            )
        return ParsedModule(
            filename=filename,
            source_lines=source_lines,
            noqa_lines=noqa_lines,
            module=module,
            tree=tree,
        )

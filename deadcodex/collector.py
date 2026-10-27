"""AST definition, usage, import, and call collection boundary."""

from deadcodex.parser import ParsedModule


class AstCollector:
    def collect(self, parsed_module: ParsedModule) -> None:
        raise NotImplementedError


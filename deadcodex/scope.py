import ast

from deadcodex import lines
from deadcodex.model import ScopeKind


class ScopeCollector(ast.NodeVisitor):
    """Build lexical class and function scopes without changing analysis."""

    def collect(self, module, tree):
        module.scope.first_lineno = 1
        module.scope.last_lineno = (
            lines.get_last_line_number(tree.body[-1]) if tree.body else 1
        )
        self._module = module
        self._scope_stack = [module.scope]
        self.visit(tree)
        return module.scope

    @property
    def current_scope(self):
        return self._scope_stack[-1]

    def visit(self, node):
        self._module.scope_by_node_id[id(node)] = self.current_scope
        return super().visit(node)

    def _visit_named_scope(self, node, kind):
        scope = self.current_scope.add_child(
            node.name,
            kind,
            first_lineno=lines.get_first_line_number(node),
            last_lineno=lines.get_last_line_number(node),
        )
        self._scope_stack.append(scope)
        try:
            self.generic_visit(node)
        finally:
            self._scope_stack.pop()

    def visit_ClassDef(self, node):
        self._visit_named_scope(node, ScopeKind.CLASS)

    def visit_FunctionDef(self, node):
        self._visit_named_scope(node, ScopeKind.FUNCTION)

    def visit_AsyncFunctionDef(self, node):
        self._visit_named_scope(node, ScopeKind.FUNCTION)

import ast

from deadcodex import lines, utils
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
        if (
            kind is ScopeKind.FUNCTION
            and self.current_scope.kind is ScopeKind.CLASS
        ):
            args = node.args.posonlyargs or node.args.args
            decorators = {
                utils.get_decorator_name(d) for d in node.decorator_list
            }
            if (
                args
                and args[0].arg in {"self", "cls"}
                and decorators.isdisjoint(
                    {"@staticmethod", "@builtins.staticmethod"}
                )
            ):
                scope.receiver_name = args[0].arg
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

    def visit_Name(self, node):
        if node.id == self.current_scope.receiver_name and isinstance(
            node.ctx, (ast.Store, ast.Del)
        ):
            self.current_scope.receiver_name = None

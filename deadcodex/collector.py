import ast
import re
import string
import sys
from fnmatch import fnmatch, fnmatchcase
from functools import partial
from pathlib import Path

from deadcodex import lines, noqa, utils
from deadcodex.analysis import AnalysisResult
from deadcodex.model import (
    DEFAULT_CONFIDENCE,
    CallSite,
    ImportBinding,
    ImportKind,
    Item,
    UsageKind,
    UsageReference,
)
from deadcodex.reachability import Reachability

IGNORED_VARIABLE_NAMES = {"object", "self"}
PYTEST_FUNCTION_NAMES = {
    "setup_module",
    "teardown_module",
    "setup_function",
    "teardown_function",
}
PYTEST_METHOD_NAMES = {
    "setup_class",
    "teardown_class",
    "setup_method",
    "teardown_method",
}

ERROR_CODES = {
    "attribute": "V101",
    "class": "V102",
    "function": "V103",
    "import": "V104",
    "method": "V105",
    "property": "V106",
    "variable": "V107",
    "unreachable_code": "V201",
}


def _is_special_name(name):
    return name.startswith("__") and name.endswith("__")


def _match(name, patterns, case=True):
    func = fnmatchcase if case else fnmatch
    return any(func(name, pattern) for pattern in patterns)


def _is_test_file(filename):
    return _match(
        filename.resolve(),
        ["*/test/*", "*/tests/*", "*/test*.py", "*[-_]test.py"],
        case=False,
    )


def _assigns_special_variable__all__(node):
    assert isinstance(node, ast.Assign)
    return isinstance(node.value, (ast.List, ast.Tuple)) and any(
        target.id == "__all__"
        for target in node.targets
        if isinstance(target, ast.Name)
    )


def _ignore_class(filename, class_name):
    return _is_test_file(filename) and "Test" in class_name


def _ignore_import(filename, import_name):
    """
    Ignore star-imported names since we can't detect whether they are used.
    Ignore imports from __init__.py files since they're commonly used to
    collect objects from a package.
    """
    return filename.name == "__init__.py" or import_name == "*"


def _ignore_function(filename, function_name):
    return (
        function_name in PYTEST_FUNCTION_NAMES
        or function_name.startswith("test_")
    ) and _is_test_file(filename)


def _ignore_method(filename, method_name):
    return _is_special_name(method_name) or (
        (method_name in PYTEST_METHOD_NAMES or method_name.startswith("test_"))
        and _is_test_file(filename)
    )


def _ignore_variable(filename, varname):
    """
    Ignore _ (Python idiom), _x (pylint convention) and
    __x__ (special variable or method), but not __x.
    """
    return (
        varname in IGNORED_VARIABLE_NAMES
        or (varname.startswith("_") and not varname.startswith("__"))
        or _is_special_name(varname)
    )


class AstCollector(AnalysisResult, ast.NodeVisitor):
    """Collect definitions and name usages from parsed Python modules."""

    def __init__(
        self, verbose=False, ignore_names=None, ignore_decorators=None
    ):
        AnalysisResult.__init__(self, verbose=verbose)
        self.verbose = verbose
        self.ignore_names = ignore_names or []
        self.ignore_decorators = ignore_decorators or []
        self.filename = Path()
        self.code = []
        self.noqa_lines = {}
        self.current_module = None

        report = partial(
            self._define,
            collection=self.unreachable_code,
            confidence=100,
        )
        self.reachability = Reachability(report=report)

    def prepare_module(self, module):
        """Make one parsed module the active collection context."""
        self.filename = module.filename
        self.code = module.source_lines
        self.noqa_lines = module.noqa_lines
        self.current_module = module.module

    def collect(self, module):
        """Collect analysis facts from a successfully parsed module."""
        if module.tree is None:
            raise ValueError("Cannot collect a module without an AST.")
        self.prepare_module(module)
        try:
            self.visit(module.tree)
        finally:
            # Reachability has module-local state which must not leak into the
            # next file. Collected definitions and usages remain cumulative.
            self.reachability.reset()

    def _log(self, *args, file=None, force=False):
        if self.verbose or force:
            file = file or sys.stdout
            try:
                print(*args, file=file)
            except UnicodeEncodeError:
                # Some terminals can't print Unicode symbols.
                text = " ".join(map(str, args))
                print(text.encode(), file=file)

    def _add_aliases(self, node):
        """
        We delegate to this method instead of using visit_alias() to have
        access to line numbers and to filter imports from __future__.
        """
        assert isinstance(node, (ast.Import, ast.ImportFrom))
        for name_and_alias in node.names:
            # Store only top-level module name ("os.path" -> "os").
            # We can't easily detect when "os.path" is used.
            name = name_and_alias.name.partition(".")[0]
            alias = name_and_alias.asname
            if self.current_module is not None:
                if isinstance(node, ast.Import):
                    binding = ImportBinding(
                        kind=ImportKind.MODULE,
                        bound_name=alias or name,
                        module_name=name_and_alias.name,
                        imported_name=None,
                        level=0,
                        alias=alias,
                        first_lineno=lines.get_first_line_number(node),
                    )
                else:
                    binding = ImportBinding(
                        kind=ImportKind.SYMBOL,
                        bound_name=alias or name_and_alias.name,
                        module_name=node.module,
                        imported_name=name_and_alias.name,
                        level=node.level,
                        alias=alias,
                        first_lineno=lines.get_first_line_number(node),
                    )
                self.current_module.imports.append(binding)
            self._define(
                self.defined_imports,
                alias or name,
                node,
                confidence=90,
                ignore=_ignore_import,
            )
            if alias is not None:
                self.used_names.add(name_and_alias.name)

    def _define(
        self,
        collection,
        name,
        first_node,
        last_node=None,
        message="",
        confidence=DEFAULT_CONFIDENCE,
        ignore=None,
        decorators=(),
    ):
        def ignored(lineno):
            return (
                (ignore and ignore(self.filename, name))
                or _match(name, self.ignore_names)
                or noqa.ignore_line(self.noqa_lines, lineno, ERROR_CODES[typ])
            )

        last_node = last_node or first_node
        typ = collection.typ
        first_lineno = lines.get_first_line_number(first_node)

        if ignored(first_lineno):
            self._log(f'Ignoring {typ} "{name}"')
        else:
            qualified_name = None
            if self.current_module is not None:
                scope = self.current_module.scope_for_node(first_node)
                qualified_name = scope.qualified_name.child(name)
            collection.append(
                Item(
                    name,
                    typ,
                    self.filename,
                    first_lineno,
                    lines.get_last_line_number(last_node),
                    message=message,
                    confidence=confidence,
                    qualified_name=qualified_name,
                    decorators=decorators,
                )
            )

    def _define_variable(self, name, node, confidence=DEFAULT_CONFIDENCE):
        self._define(
            self.defined_vars,
            name,
            node,
            confidence=confidence,
            ignore=_ignore_variable,
        )

    def visit_arg(self, node):
        """Function argument"""
        self._define_variable(node.arg, node, confidence=100)

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

    def visit_Attribute(self, node):
        if isinstance(node.ctx, ast.Store):
            self._define(self.defined_attrs, node.attr, node)
        elif isinstance(node.ctx, ast.Load):
            self.used_names.add(node.attr)
            self._record_usage(
                node,
                kind=UsageKind.ATTRIBUTE,
                parts=self._attribute_parts(node),
            )

    def visit_BinOp(self, node):
        """
        Parse variable names in old format strings:

        "%(my_var)s" % locals()
        """
        if (
            utils.is_ast_string(node.left)
            and isinstance(node.op, ast.Mod)
            and self._is_locals_call(node.right)
        ):
            self.used_names |= set(re.findall(r"%\((\w+)\)", node.left.value))

    def visit_Call(self, node):
        self._record_call(node)

        # Count getattr/hasattr(x, "some_attr", ...) as usage of some_attr.
        if isinstance(node.func, ast.Name) and (
            (node.func.id == "getattr" and 2 <= len(node.args) <= 3)
            or (node.func.id == "hasattr" and len(node.args) == 2)
        ):
            attr_name_arg = node.args[1]
            if utils.is_ast_string(attr_name_arg):
                self.used_names.add(attr_name_arg.value)

        # Parse variable names in new format strings:
        # "{my_var}".format(**locals())
        if (
            isinstance(node.func, ast.Attribute)
            and utils.is_ast_string(node.func.value)
            and node.func.attr == "format"
            and any(
                kw.arg is None and self._is_locals_call(kw.value)
                for kw in node.keywords
            )
        ):
            self._handle_new_format_string(node.func.value.value)

    def _handle_new_format_string(self, s):
        def is_identifier(name):
            return bool(re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", name))

        parser = string.Formatter()
        try:
            names = [name for _, name, _, _ in parser.parse(s) if name]
        except ValueError:
            # Invalid format string.
            names = []

        for field_name in names:
            # Remove brackets and their contents: "a[0][b].c[d].e" -> "a.c.e",
            # then split the resulting string: "a.b.c" -> ["a", "b", "c"]
            variables = re.sub(r"\[\w*\]", "", field_name).split(".")
            for variable in variables:
                if is_identifier(variable):
                    self.used_names.add(variable)

    @staticmethod
    def _is_locals_call(node):
        """Return True if the node is `locals()`."""
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "locals"
            and not node.args
            and not node.keywords
        )

    def visit_ClassDef(self, node):
        decorator_names = tuple(
            utils.get_decorator_name(decorator)
            for decorator in node.decorator_list
        )
        if any(
            _match(name, self.ignore_decorators) for name in decorator_names
        ):
            self._log(f'Ignoring class "{node.name}" (decorator whitelisted)')
        else:
            self._define(
                self.defined_classes,
                node.name,
                node,
                ignore=_ignore_class,
                decorators=decorator_names,
            )

    def visit_FunctionDef(self, node):
        decorator_names = [
            utils.get_decorator_name(decorator)
            for decorator in node.decorator_list
        ]

        first_arg = node.args.args[0].arg if node.args.args else None

        if "@property" in decorator_names:
            typ = "property"
        elif (
            "@staticmethod" in decorator_names
            or "@classmethod" in decorator_names
            or first_arg == "self"
        ):
            typ = "method"
        else:
            typ = "function"

        if any(
            _match(name, self.ignore_decorators) for name in decorator_names
        ):
            self._log(f'Ignoring {typ} "{node.name}" (decorator whitelisted)')
        elif typ == "property":
            self._define(
                self.defined_props,
                node.name,
                node,
                decorators=decorator_names,
            )
        elif typ == "method":
            self._define(
                self.defined_methods,
                node.name,
                node,
                ignore=_ignore_method,
                decorators=decorator_names,
            )
        else:
            self._define(
                self.defined_funcs,
                node.name,
                node,
                ignore=_ignore_function,
                decorators=decorator_names,
            )

    def visit_Import(self, node):
        self._add_aliases(node)

    def visit_ImportFrom(self, node):
        if node.module != "__future__":
            self._add_aliases(node)

    def visit_Name(self, node):
        if (
            isinstance(node.ctx, (ast.Load, ast.Del))
            and node.id not in IGNORED_VARIABLE_NAMES
        ):
            self.used_names.add(node.id)
            self._record_usage(node, kind=UsageKind.NAME, parts=(node.id,))
        elif isinstance(node.ctx, (ast.Param, ast.Store)):
            self._define_variable(node.id, node)

    def _record_usage(self, node, kind, parts):
        if self.current_module is None:
            return
        scope = self.current_module.scope_for_node(node)
        self.current_module.references.append(
            UsageReference(
                kind=kind,
                name=parts[-1],
                parts=parts,
                scope_name=scope.qualified_name,
                filename=self.filename,
                first_lineno=lines.get_first_line_number(node),
            )
        )

    def _record_call(self, node):
        if self.current_module is None:
            return
        if isinstance(node.func, ast.Name):
            callee_parts = (node.func.id,)
        elif isinstance(node.func, ast.Attribute):
            callee_parts = self._attribute_parts(node.func)
        else:
            callee_parts = ()
        scope = self.current_module.scope_for_node(node)
        self.current_module.calls.append(
            CallSite(
                caller=scope.qualified_name,
                callee_parts=callee_parts,
                filename=self.filename,
                first_lineno=lines.get_first_line_number(node),
            )
        )

    @staticmethod
    def _attribute_parts(node):
        parts = []
        value = node
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            parts.append(value.id)
        return tuple(reversed(parts))

    def visit_Assign(self, node):
        if _assigns_special_variable__all__(node):
            assert isinstance(node.value, (ast.List, ast.Tuple))
            for element in node.value.elts:
                if utils.is_ast_string(element):
                    self.used_names.add(element.value)

    def visit_MatchClass(self, node):
        for keyword_attribute in node.kwd_attrs:
            self.used_names.add(keyword_attribute)

    def visit(self, node):
        # Visit children nodes first to allow recursive reachability analysis.
        self.generic_visit(node)

        self.reachability.visit(node)

        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, None)
        if self.verbose:
            lineno = getattr(node, "lineno", 1)
            line = self.code[lineno - 1] if self.code else ""
            self._log(lineno, ast.dump(node), line)
        if visitor:
            visitor(node)

        # There isn't a clean subset of node types that might have type
        # comments, so just check all of them.
        type_comment = getattr(node, "type_comment", None)
        if type_comment is not None:
            mode = (
                "func_type"
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                else "eval"
            )
            self.visit(
                ast.parse(type_comment, filename="<type_comment>", mode=mode)
            )

    def generic_visit(self, node):
        """Called if no explicit visitor function exists for a node."""
        for _, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self.visit(item)
            elif isinstance(value, ast.AST):
                self.visit(value)

from deadcodex import utils
from deadcodex.model import Item, ResolutionStatus


def _get_unused_items(defined_items, used_names):
    unused_items = [
        item for item in set(defined_items) if item.name not in used_names
    ]
    unused_items.sort(key=lambda item: item.name.lower())
    return unused_items


class AnalysisResult:
    """Store definitions and usages collected across analyzed modules."""

    def __init__(self, verbose=False):
        def get_list(typ):
            return utils.LoggingList(typ, verbose)

        self.defined_attrs = get_list("attribute")
        self.defined_classes = get_list("class")
        self.defined_funcs = get_list("function")
        self.defined_imports = get_list("import")
        self.defined_methods = get_list("method")
        self.defined_props = get_list("property")
        self.defined_vars = get_list("variable")
        self.unreachable_code = get_list("unreachable_code")
        self.used_names = utils.LoggingSet("name", verbose)
        self.dynamic_used_names = set()

    @property
    def defined_items(self):
        return (
            self.defined_attrs
            + self.defined_classes
            + self.defined_funcs
            + self.defined_imports
            + self.defined_methods
            + self.defined_props
            + self.defined_vars
        )

    def get_unused_code(
        self, min_confidence=0, sort_by_size=False
    ) -> list[Item]:
        """Return an ordered list of unused items."""
        if not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be between 0 and 100.")

        def by_name(item):
            return str(item.filename).lower(), item.first_lineno

        def by_size(item):
            return item.size, *by_name(item)

        unused_code = (
            self.unused_attrs
            + self.unused_classes
            + self.unused_funcs
            + self.unused_imports
            + self.unused_methods
            + self.unused_props
            + self.unused_vars
            + self.unreachable_code
        )
        confidently_unused = [
            item for item in unused_code if item.confidence >= min_confidence
        ]
        return sorted(
            confidently_unused, key=by_size if sort_by_size else by_name
        )

    def get_unused_code_qualified(
        self, references, min_confidence=0, sort_by_size=False
    ) -> list[Item]:
        """Analyze collected items against the supplied resolved references."""
        return ProjectAnalysis().analyze_references(
            references, self, min_confidence, sort_by_size
        )

    @property
    def unused_classes(self):
        return _get_unused_items(self.defined_classes, self.used_names)

    @property
    def unused_funcs(self):
        return _get_unused_items(self.defined_funcs, self.used_names)

    @property
    def unused_imports(self):
        return _get_unused_items(self.defined_imports, self.used_names)

    @property
    def unused_methods(self):
        return _get_unused_items(self.defined_methods, self.used_names)

    @property
    def unused_props(self):
        return _get_unused_items(self.defined_props, self.used_names)

    @property
    def unused_vars(self):
        return _get_unused_items(self.defined_vars, self.used_names)

    @property
    def unused_attrs(self):
        return _get_unused_items(self.defined_attrs, self.used_names)


class ProjectAnalysis:
    """Find unused definitions from already resolved project references.

    Qualified targets distinguish identical names across modules and scopes.
    Unresolved reads and dynamic names retain conservative name protection.
    This is reference usage, not entry-point reachability.
    """

    def analyze(
        self, project, result, min_confidence=0, sort_by_size=False
    ) -> list[Item]:
        references = (
            reference
            for module in project.modules
            for reference in module.references
        )
        return self.analyze_references(
            references, result, min_confidence, sort_by_size
        )

    def analyze_references(
        self, references, result, min_confidence=0, sort_by_size=False
    ) -> list[Item]:
        if not 0 <= min_confidence <= 100:
            raise ValueError("min_confidence must be between 0 and 100.")

        used_targets = set()
        used_imports = set()
        uncertain_names = set()
        for reference in references:
            if reference.status is ResolutionStatus.PENDING:
                raise ValueError("Resolve references before analysis.")
            if reference.status is ResolutionStatus.RESOLVED:
                if reference.target is not None:
                    used_targets.add(reference.target)
            elif reference.status in {
                ResolutionStatus.UNRESOLVED,
                ResolutionStatus.AMBIGUOUS,
            }:
                uncertain_names.add(reference.name)
            used_imports.update(
                (
                    reference.filename.resolve(),
                    binding.first_lineno,
                    binding.bound_name,
                )
                for binding in reference.import_bindings
            )

        # Names recorded by __all__, getattr, and other dynamic usage
        # heuristics remain protected even when a static reference shares
        # the same spelling.
        dynamic_names = result.dynamic_used_names
        fallback_names = uncertain_names | dynamic_names

        def is_used(item):
            if item.qualified_name is None:
                return item.name in result.used_names
            if item.typ == "import":
                return (
                    item.filename.resolve(),
                    item.first_lineno,
                    item.name,
                ) in used_imports or item.name in dynamic_names
            return (
                item.qualified_name in used_targets
                or item.name in fallback_names
            )

        unused = {item for item in result.defined_items if not is_used(item)}
        unused.update(result.unreachable_code)

        def sort_key(item):
            location = (str(item.filename).lower(), item.first_lineno)
            return (item.size, *location) if sort_by_size else location

        return sorted(
            (item for item in unused if item.confidence >= min_confidence),
            key=sort_key,
        )

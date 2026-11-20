"""Resolve imports and name references across project modules."""

import builtins
from collections import defaultdict

from deadcodex.model import (
    ImportKind,
    ProjectModel,
    QualifiedName,
    ResolutionStatus,
    ScopeKind,
)


def _qualified(parts):
    parts = tuple(part for part in parts if part)
    return QualifiedName(parts) if parts else None


def _extend(name, dotted_name):
    if name is None:
        return None
    result = name
    for part in dotted_name.split("."):
        if part:
            result = result.child(part)
    return result


class _ProjectIndex:
    def __init__(self, project, definitions=()):
        self.modules_by_name = defaultdict(list)
        for module in project.modules:
            self.modules_by_name[module.qualified_name].append(module)

        self.top_level_names = {name.parts[0] for name in self.modules_by_name}
        self.definition_names = set()
        self.definitions_by_qualified_name = defaultdict(list)
        for definition in definitions:
            name = getattr(definition, "qualified_name", None)
            if name is None:
                continue
            self.definition_names.add(name)
            self.definitions_by_qualified_name[name].append(definition)

    def module_status(self, name):
        exact_matches = self.modules_by_name.get(name, ())
        if len(exact_matches) == 1:
            return ResolutionStatus.RESOLVED
        if len(exact_matches) > 1:
            return ResolutionStatus.AMBIGUOUS

        prefix = name.parts
        if any(
            candidate.parts[: len(prefix)] == prefix
            for candidate in self.modules_by_name
        ):
            return ResolutionStatus.RESOLVED
        return ResolutionStatus.UNRESOLVED

    def qualified_status(self, name):
        matches = len(self.modules_by_name.get(name, ()))
        matches += int(name in self.definition_names)
        if matches == 1:
            return ResolutionStatus.RESOLVED
        if matches > 1:
            return ResolutionStatus.AMBIGUOUS
        return self.module_status(name)


class ImportResolver:
    """Resolve collected imports against modules and project definitions."""

    def __init__(self, definitions=()):
        self.definitions = tuple(definitions)

    def resolve(self, project: ProjectModel) -> None:
        index = _ProjectIndex(project, self.definitions)
        for module in project.modules:
            for binding in module.imports:
                self._resolve_binding(module, binding, index)

    def _resolve_binding(self, module, binding, index):
        binding.status = ResolutionStatus.PENDING
        binding.target = None
        imported_module = self._imported_module_name(module, binding)
        if imported_module is None:
            binding.status = ResolutionStatus.UNRESOLVED
            return

        if binding.kind is ImportKind.MODULE:
            self._resolve_module_import(binding, imported_module, index)
        else:
            self._resolve_symbol_import(binding, imported_module, index)

    @staticmethod
    def _imported_module_name(module, binding):
        module_parts = tuple((binding.module_name or "").split("."))
        module_parts = tuple(part for part in module_parts if part)
        if binding.level == 0:
            return _qualified(module_parts)

        current_parts = module.qualified_name.parts
        package_parts = (
            current_parts if module.is_package else current_parts[:-1]
        )
        parents_to_remove = binding.level - 1
        if parents_to_remove >= len(package_parts):
            return None
        if parents_to_remove:
            package_parts = package_parts[:-parents_to_remove]
        return _qualified((*package_parts, *module_parts))

    @staticmethod
    def _is_external(name, binding, index):
        return (
            binding.level == 0 and name.parts[0] not in index.top_level_names
        )

    def _resolve_module_import(self, binding, imported_module, index):
        status = index.module_status(imported_module)
        if status is ResolutionStatus.UNRESOLVED and self._is_external(
            imported_module, binding, index
        ):
            status = ResolutionStatus.EXTERNAL
        binding.status = status
        if status in {ResolutionStatus.RESOLVED, ResolutionStatus.EXTERNAL}:
            binding.target = imported_module

    def _resolve_symbol_import(self, binding, imported_module, index):
        module_status = index.module_status(imported_module)
        if module_status is ResolutionStatus.UNRESOLVED:
            if self._is_external(imported_module, binding, index):
                binding.status = ResolutionStatus.EXTERNAL
                binding.target = _extend(
                    imported_module, binding.imported_name or ""
                )
            else:
                binding.status = ResolutionStatus.UNRESOLVED
            return
        if module_status is ResolutionStatus.AMBIGUOUS:
            binding.status = ResolutionStatus.AMBIGUOUS
            return

        if binding.imported_name == "*":
            binding.status = ResolutionStatus.RESOLVED
            binding.target = imported_module
            return

        target = _extend(imported_module, binding.imported_name or "")
        binding.status = index.qualified_status(target)
        if binding.status is ResolutionStatus.RESOLVED:
            binding.target = target


class ReferenceResolver:
    """Resolve references through lexical definitions and import bindings."""

    def __init__(self, definitions=()):
        self.definitions = tuple(definitions)

    def resolve(self, project: ProjectModel) -> None:
        if any(
            binding.status is ResolutionStatus.PENDING
            for module in project.modules
            for binding in module.imports
        ):
            ImportResolver(self.definitions).resolve(project)

        index = _ProjectIndex(project, self.definitions)
        for module in project.modules:
            imports = self._imports_by_bound_name(module)
            for reference in module.references:
                self._resolve_reference(module, reference, imports, index)

    @staticmethod
    def _imports_by_bound_name(module):
        imports = defaultdict(list)
        for binding in module.imports:
            imports[binding.bound_name].append(binding)
        return imports

    def _resolve_reference(self, module, reference, imports, index):
        reference.status = ResolutionStatus.PENDING
        reference.target = None
        reference.binding_target = None
        if not reference.parts:
            reference.status = ResolutionStatus.UNRESOLVED
            return

        if self._resolve_lexical_reference(module, reference, imports, index):
            return

        if reference.parts[0] in vars(builtins):
            reference.status = ResolutionStatus.EXTERNAL
            reference.target = _qualified(("builtins", *reference.parts))
        else:
            reference.status = ResolutionStatus.UNRESOLVED

    @staticmethod
    def _active_bindings(bindings, reference_line):
        prior = [
            binding
            for binding in bindings
            if binding.first_lineno <= reference_line
        ]
        candidates = prior or list(bindings)
        if not candidates:
            return ()
        latest_line = max(binding.first_lineno for binding in candidates)
        return tuple(
            binding
            for binding in candidates
            if binding.first_lineno == latest_line
        )

    def _resolve_imported_reference(self, reference, bindings, index):
        statuses = {binding.status for binding in bindings}
        binding_targets = {
            binding.target
            for binding in bindings
            if binding.target is not None
        }
        if len(binding_targets) == 1:
            reference.binding_target = next(iter(binding_targets))

        if ResolutionStatus.AMBIGUOUS in statuses or len(statuses) > 1:
            reference.status = ResolutionStatus.AMBIGUOUS
            return
        status = next(iter(statuses))
        if status is ResolutionStatus.UNRESOLVED:
            reference.status = status
            return

        targets = {
            self._reference_target(binding, reference.parts)
            for binding in bindings
        }
        targets.discard(None)
        if len(targets) != 1:
            reference.status = ResolutionStatus.AMBIGUOUS
            return
        target = next(iter(targets))

        if status is ResolutionStatus.EXTERNAL:
            reference.status = status
            reference.target = target
            return

        resolved_status = index.qualified_status(target)
        reference.status = resolved_status
        if resolved_status is ResolutionStatus.RESOLVED:
            reference.target = target

    @staticmethod
    def _reference_target(binding, parts):
        if binding.target is None:
            return None
        if binding.kind is ImportKind.MODULE and binding.alias is None:
            base = _qualified((binding.bound_name,))
        else:
            base = binding.target
        result = base
        for part in parts[1:]:
            result = result.child(part)
        return result

    @staticmethod
    def _lexical_scopes(module, reference):
        scope = module.scope_named(reference.scope_name)
        if scope is None:
            yield module.qualified_name
            return
        first = True
        while scope is not None:
            # A class namespace is not an enclosing lexical scope for methods.
            if first or scope.kind is not ScopeKind.CLASS:
                yield scope.qualified_name
            first = False
            scope = scope.parent

    def _resolve_lexical_reference(self, module, reference, imports, index):
        for scope_name in self._lexical_scopes(module, reference):
            local_name = scope_name.child(reference.parts[0])
            definitions = index.definitions_by_qualified_name.get(
                local_name, ()
            )
            bindings = self._active_bindings(
                [
                    binding
                    for binding in imports.get(reference.parts[0], ())
                    if (binding.scope_name or module.qualified_name)
                    == scope_name
                ],
                reference.first_lineno,
            )
            if bindings and definitions:
                prior_definitions = [
                    item.first_lineno
                    for item in definitions
                    if item.first_lineno <= reference.first_lineno
                ]
                if prior_definitions and max(prior_definitions) >= (
                    bindings[0].first_lineno
                ):
                    bindings = ()
            if bindings:
                self._resolve_imported_reference(reference, bindings, index)
                return True
            if definitions:
                target = _extend(local_name, ".".join(reference.parts[1:]))
                reference.status = index.qualified_status(target)
                if reference.status is ResolutionStatus.RESOLVED:
                    reference.target = target
                # An unknown attribute of a local binding must not fall back
                # to an outer import or an unrelated project definition.
                return True
        return False

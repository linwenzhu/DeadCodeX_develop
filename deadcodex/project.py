import os
from pathlib import Path

from deadcodex import utils
from deadcodex.model import ModuleModel, ProjectModel, QualifiedName


class ProjectLoader:
    """Discover Python modules and derive stable dotted module names."""

    def load(self, paths):
        requested_paths = [Path(path).resolve() for path in paths]
        modules = []
        source_roots = []

        for requested_path in requested_paths:
            source_root = self._source_root(requested_path)
            source_roots.append(source_root)
            modules.extend(
                self.module_from_path(module_path, source_root=source_root)
                for module_path in utils.get_modules([requested_path])
            )

        project = ProjectModel(
            root=self._common_root(source_roots), modules=modules
        )
        return project

    def read_module(self, module):
        return utils.read_file(module.path)

    def module_from_path(self, path, source_root=None):
        path = Path(path)
        source_root = (
            Path(source_root)
            if source_root is not None
            else self._source_root(path)
        )
        qualified_name = self._qualified_name(path, source_root)
        return ModuleModel(
            path=path,
            qualified_name=qualified_name,
            source_root=source_root,
            is_package=path.name == "__init__.py",
        )

    @staticmethod
    def in_memory_module():
        return ModuleModel(
            path=Path(),
            qualified_name=QualifiedName(("<memory>",)),
            source_root=Path(),
        )

    @staticmethod
    def _source_root(path):
        path = Path(path)
        if path.is_dir():
            return path.parent if (path / "__init__.py").is_file() else path

        parent = path.parent
        while (parent / "__init__.py").is_file():
            parent = parent.parent
        return parent

    @staticmethod
    def _qualified_name(path, source_root):
        try:
            relative_path = path.relative_to(source_root)
        except ValueError:
            relative_path = Path(path.name)

        parts = list(relative_path.parts)
        if parts:
            parts[-1] = relative_path.stem
        if parts and parts[-1] == "__init__":
            parts.pop()
        if not parts:
            parts = [path.parent.name or path.stem or "<memory>"]
        return QualifiedName.from_string(".".join(parts))

    @staticmethod
    def _common_root(source_roots):
        if not source_roots:
            return Path()
        try:
            return Path(os.path.commonpath(source_roots))
        except ValueError:
            return Path()

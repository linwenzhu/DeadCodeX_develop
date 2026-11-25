import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BaselineEntry:
    """A stable finding identity stored in a baseline file."""

    fingerprint: str
    kind: str
    name: str
    qualified_name: str
    filename: str
    first_lineno: int

    @classmethod
    def from_item(cls, item, root):
        filename = _relative_filename(item.filename, root)
        qualified_name = (
            str(item.qualified_name) if item.qualified_name is not None else ""
        )
        identity = qualified_name or f"{item.name}:{item.first_lineno}"
        fingerprint = _fingerprint(item.typ, filename, identity)
        return cls(
            fingerprint=fingerprint,
            kind=item.typ,
            name=item.name,
            qualified_name=qualified_name,
            filename=filename,
            first_lineno=item.first_lineno,
        )

    def to_dict(self):
        return {
            "fingerprint": self.fingerprint,
            "kind": self.kind,
            "name": self.name,
            "qualified_name": self.qualified_name or None,
            "filename": self.filename,
            "first_lineno": self.first_lineno,
        }


@dataclass(frozen=True)
class Baseline:
    """Known findings which should be hidden from normal reports."""

    entries: tuple[BaselineEntry, ...]

    @classmethod
    def from_items(cls, items, root):
        entries = {}
        for item in items:
            entry = BaselineEntry.from_item(item, root)
            entries[entry.fingerprint] = entry
        return cls(tuple(entries[key] for key in sorted(entries)))

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"Baseline file does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("format") != "deadcodex-baseline":
                raise ValueError("Unknown baseline format.")
            if payload.get("version") != 1:
                raise ValueError("Unsupported baseline version.")
            entries = tuple(
                BaselineEntry(
                    fingerprint=entry["fingerprint"],
                    kind=entry["kind"],
                    name=entry["name"],
                    qualified_name=entry.get("qualified_name") or "",
                    filename=entry["filename"],
                    first_lineno=entry["first_lineno"],
                )
                for entry in payload["entries"]
            )
        except (
            AttributeError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError(f"Invalid baseline file: {path}") from error
        return cls(entries)

    def filter(self, items, root):
        known = {entry.fingerprint for entry in self.entries}
        return [
            item
            for item in items
            if BaselineEntry.from_item(item, root).fingerprint not in known
        ]

    def write(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "format": "deadcodex-baseline",
            "version": 1,
            "entries": [entry.to_dict() for entry in self.entries],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _relative_filename(filename, root):
    filename = Path(filename)
    try:
        return filename.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return filename.resolve().as_posix()


def _fingerprint(kind, filename, identity):
    value = "\0".join((kind, filename, identity)).encode()
    return hashlib.sha256(value).hexdigest()

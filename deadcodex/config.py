"""Command-line and project configuration boundary."""

from __future__ import annotations

from typing import Any, Sequence


def make_config(argv: Sequence[str] | None = None) -> dict[str, Any]:
    raise NotImplementedError


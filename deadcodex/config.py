"""Command-line and project configuration boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def make_config(argv: Sequence[str] | None = None) -> dict[str, Any]:
    raise NotImplementedError

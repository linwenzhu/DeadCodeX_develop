"""Basic single-file input for DeadCodex's compatibility mode."""

import math
from collections import defaultdict

VISIBLE_LIMIT = 3
DOCUMENTATION_ONLY = "kept intentionally"  # noqa: V107


def double(value):
    return value * 2


async def unused_async_worker():
    return "never awaited"


def unused_function():
    return "legacy"
    print("unreachable statement")


class ActiveCounter:
    def __init__(self):
        self.total = 0

    @property
    def value(self):
        return self.total

    @property
    def unused_property(self):
        return -1

    def add(self, amount):
        self.total += amount

    def unused_method(self):
        return self.total


class UnusedFormatter:
    def render(self, value):
        return f"value={value}"


def main():
    counter = ActiveCounter()
    for number in range(VISIBLE_LIMIT):
        counter.add(number)
    return double(counter.value)


if __name__ == "__main__":
    print(main())

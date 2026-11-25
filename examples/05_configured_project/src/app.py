"""Application selected as an entry point by pyproject.toml."""

from helpers import calculate_total


def main():
    return calculate_total([2, 3, 5])


def deprecated_command():
    message = "This command is no longer registered."
    return message

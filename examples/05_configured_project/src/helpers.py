"""Used and unused helpers for the configuration example."""


def calculate_total(values):
    return sum(values)


def legacy_calculation(values):
    total = 0
    for value in values:
        total += value
    return total

"""Formatting helpers used through an aliased relative import."""


def format_total(value):
    return f"${value:.2f}"


def legacy_currency(value):
    return f"USD {value}"

"""Tax calculations referenced through a module attribute."""


def add_tax(value):
    return round(value * 1.2, 2)


def obsolete_tax(value):
    return value * 1.15

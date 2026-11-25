"""Checkout service with relative module and symbol imports."""

from . import taxes
from .formatting import format_total as render_total


def checkout(customer, amounts):
    total = taxes.add_tax(sum(amounts))
    return f"{customer}: {render_total(total)}"

"""Conversão de valores para BRL."""

from __future__ import annotations

from decimal import Decimal

from ..exceptions import InputFileError


def convert_to_brl(amount: Decimal, currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Converte um valor na moeda informada para BRL usando a taxa da tabela."""
    rate = rates.get(currency)
    if rate is None:
        raise InputFileError(f"moeda sem taxa de câmbio: {currency}")
    return amount * rate

"""
Input validation for CLI arguments before they reach the API layer.
All validators raise ValueError with a clear, user-facing message on failure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET"}


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────


def validate_symbol(symbol: str) -> str:
    """
    Return the symbol uppercased.
    Raises ValueError for empty or obviously invalid values.
    """
    if not symbol or not symbol.strip():
        raise ValueError("Symbol cannot be empty.")
    cleaned = symbol.strip().upper()
    if not cleaned.isalnum():
        raise ValueError(
            f"Symbol '{cleaned}' contains invalid characters. "
            "Expected alphanumeric only (e.g. BTCUSDT)."
        )
    return cleaned


def validate_side(side: str) -> str:
    """Return the side uppercased or raise ValueError."""
    cleaned = side.strip().upper()
    if cleaned not in VALID_SIDES:
        raise ValueError(
            f"Invalid side '{cleaned}'. Must be one of: {', '.join(sorted(VALID_SIDES))}."
        )
    return cleaned


def validate_order_type(order_type: str) -> str:
    """Return the order type uppercased or raise ValueError."""
    cleaned = order_type.strip().upper()
    if cleaned not in VALID_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{cleaned}'. "
            f"Must be one of: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    return cleaned


def validate_quantity(quantity: str | float) -> Decimal:
    """
    Parse and return quantity as Decimal.
    Raises ValueError for non-positive or non-numeric values.
    """
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValueError(f"Quantity must be greater than zero (got {qty}).")
    return qty


def validate_price(price: Optional[str | float], order_type: str) -> Optional[Decimal]:
    """
    Parse and return price as Decimal when required, or None for MARKET orders.
    Raises ValueError if price is missing for LIMIT / STOP_MARKET orders,
    or if the value is non-positive / non-numeric.
    """
    order_type_upper = order_type.strip().upper()
    requires_price = order_type_upper in {"LIMIT", "STOP_MARKET"}

    if price is None or str(price).strip() == "":
        if requires_price:
            raise ValueError(
                f"Price is required for {order_type_upper} orders."
            )
        return None  # MARKET — price not needed

    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"Price '{price}' is not a valid number.")
    if p <= 0:
        raise ValueError(f"Price must be greater than zero (got {p}).")
    return p


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: Optional[str | float] = None,
) -> dict:
    """
    Run all validators and return a clean params dict, or raise ValueError on
    the first validation error encountered.

    Returns:
        {
            "symbol":     str,
            "side":       str,
            "order_type": str,
            "quantity":   Decimal,
            "price":      Decimal | None,
        }
    """
    return {
        "symbol":     validate_symbol(symbol),
        "side":       validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity":   validate_quantity(quantity),
        "price":      validate_price(price, order_type),
    }

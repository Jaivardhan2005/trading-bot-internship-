"""
Order placement logic — sits between the CLI and the raw API client.
Converts validated domain objects into Binance API parameters and returns
a clean, normalised OrderResult.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Dict, Optional

from bot.client import BinanceFuturesClient
from bot.logging_config import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class OrderResult:
    """Normalised order response returned to the CLI layer."""

    success: bool
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    status: Optional[str] = None
    orig_qty: Optional[str] = None
    executed_qty: Optional[str] = None
    avg_price: Optional[str] = None
    price: Optional[str] = None
    time_in_force: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def pretty(self) -> str:
        """Human-readable summary for CLI output."""
        if not self.success:
            return f"  ✗  Order FAILED: {self.error_message}"

        lines = [
            f"  ✓  Order placed successfully",
            f"     Order ID      : {self.order_id}",
            f"     Client Ord ID : {self.client_order_id}",
            f"     Symbol        : {self.symbol}",
            f"     Side          : {self.side}",
            f"     Type          : {self.order_type}",
            f"     Status        : {self.status}",
            f"     Orig Qty      : {self.orig_qty}",
            f"     Executed Qty  : {self.executed_qty}",
        ]
        if self.avg_price and self.avg_price != "0":
            lines.append(f"     Avg Price     : {self.avg_price}")
        if self.price and self.price != "0":
            lines.append(f"     Limit Price   : {self.price}")
        if self.time_in_force:
            lines.append(f"     Time-in-Force : {self.time_in_force}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Order manager
# ─────────────────────────────────────────────────────────────────────────────


class OrderManager:
    """
    High-level interface for creating orders.
    Translates validated Python types into Binance API parameters.
    """

    def __init__(self, client: BinanceFuturesClient) -> None:
        self._client = client

    # ── Public order methods ─────────────────────────────────────────────────

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
    ) -> OrderResult:
        """Place a MARKET order."""
        params = {
            "symbol":   symbol,
            "side":     side,
            "type":     "MARKET",
            "quantity": str(quantity),
        }
        logger.info(
            "MARKET order request | symbol=%s side=%s qty=%s",
            symbol, side, quantity,
        )
        return self._submit(params)

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        time_in_force: str = "GTC",
    ) -> OrderResult:
        """Place a LIMIT order (GTC by default)."""
        params = {
            "symbol":      symbol,
            "side":        side,
            "type":        "LIMIT",
            "quantity":    str(quantity),
            "price":       str(price),
            "timeInForce": time_in_force,
        }
        logger.info(
            "LIMIT order request | symbol=%s side=%s qty=%s price=%s tif=%s",
            symbol, side, quantity, price, time_in_force,
        )
        return self._submit(params)

    def place_stop_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal,
    ) -> OrderResult:
        """Place a STOP_MARKET order (bonus order type)."""
        params = {
            "symbol":    symbol,
            "side":      side,
            "type":      "STOP_MARKET",
            "quantity":  str(quantity),
            "stopPrice": str(stop_price),
        }
        logger.info(
            "STOP_MARKET order request | symbol=%s side=%s qty=%s stop=%s",
            symbol, side, quantity, stop_price,
        )
        return self._submit(params)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _submit(self, params: Dict[str, Any]) -> OrderResult:
        """Send order params to the client and normalise the response."""
        try:
            raw = self._client.place_order(**params)
            result = self._normalise(raw, success=True)
            logger.debug("Order response (normalised): %s", json.dumps(result.as_dict(), default=str))
            return result
        except Exception as exc:
            logger.error("Order submission failed: %s", exc, exc_info=True)
            return OrderResult(success=False, error_message=str(exc))

    @staticmethod
    def _normalise(raw: Dict[str, Any], success: bool) -> OrderResult:
        """Map raw Binance response fields to OrderResult."""
        return OrderResult(
            success=success,
            order_id=raw.get("orderId"),
            client_order_id=raw.get("clientOrderId"),
            symbol=raw.get("symbol"),
            side=raw.get("side"),
            order_type=raw.get("type"),
            status=raw.get("status"),
            orig_qty=raw.get("origQty"),
            executed_qty=raw.get("executedQty"),
            avg_price=raw.get("avgPrice"),
            price=raw.get("price"),
            time_in_force=raw.get("timeInForce"),
            raw_response=raw,
        )

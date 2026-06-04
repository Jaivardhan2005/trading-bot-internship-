"""
Low-level Binance Futures REST client.
Handles HMAC-SHA256 request signing, timestamp injection, and HTTP transport.
All network/API errors are caught here and re-raised as domain exceptions.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import urllib.parse
from typing import Any, Dict, Optional

import requests

from bot.logging_config import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────


class BinanceAPIError(Exception):
    """Raised when the Binance API returns an error payload."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceNetworkError(Exception):
    """Raised on connection / timeout failures."""


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────


class BinanceFuturesClient:
    """
    Thin wrapper around the Binance USDT-M Futures REST API.

    Parameters
    ----------
    api_key:    Binance API key.
    api_secret: Binance API secret (used for HMAC signing).
    base_url:   Base URL; defaults to the public testnet endpoint.
    timeout:    HTTP request timeout in seconds.
    """

    DEFAULT_BASE_URL = "https://testnet.binancefuture.com"

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 10,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")

        self._api_key = api_key
        self._api_secret = api_secret.encode()          # bytes for hmac
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        logger.debug("BinanceFuturesClient initialised (base_url=%s)", self._base_url)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _timestamp(self) -> int:
        return int(time.time() * 1000)

    def _sign(self, params: Dict[str, Any]) -> str:
        """Return HMAC-SHA256 hex digest of the query-string encoded params."""
        qs = urllib.parse.urlencode(params)
        return hmac.new(self._api_secret, qs.encode(), hashlib.sha256).hexdigest()

    def _build_signed_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Inject timestamp and signature into a copy of *params*."""
        signed = dict(params)
        signed["timestamp"] = self._timestamp()
        signed["signature"] = self._sign(signed)
        return signed

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = False,
    ) -> Any:
        """
        Execute an HTTP request and return the parsed JSON body.

        Raises
        ------
        BinanceAPIError    – API returned {"code": <negative>, "msg": ...}
        BinanceNetworkError – connection / timeout problem
        """
        url = f"{self._base_url}{path}"
        payload = params or {}

        if signed:
            payload = self._build_signed_params(payload)

        logger.debug("→ %s %s | params: %s", method.upper(), url, _redact(payload))

        try:
            response = self._session.request(
                method,
                url,
                params=payload if method.upper() == "GET" else None,
                data=payload if method.upper() == "POST" else None,
                timeout=self._timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s %s", method, url)
            raise BinanceNetworkError(f"Request timed out ({self._timeout}s)") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s %s — %s", method, url, exc)
            raise BinanceNetworkError(f"Connection error: {exc}") from exc

        logger.debug("← HTTP %s | body: %.500s", response.status_code, response.text)

        try:
            data = response.json()
        except ValueError:
            logger.error("Non-JSON response (HTTP %s): %s", response.status_code, response.text[:200])
            raise BinanceNetworkError(
                f"Non-JSON response (HTTP {response.status_code}): {response.text[:200]}"
            )

        if isinstance(data, dict) and "code" in data and data["code"] < 0:
            logger.error("API error %s: %s", data["code"], data.get("msg", ""))
            raise BinanceAPIError(data["code"], data.get("msg", "Unknown error"))

        return data

    # ── Public API methods ────────────────────────────────────────────────────

    def get_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange metadata (symbols, filters, etc.)."""
        return self._request("GET", "/fapi/v1/exchangeInfo")

    def get_account(self) -> Dict[str, Any]:
        """Fetch account details (balances, positions)."""
        return self._request("GET", "/fapi/v2/account", signed=True)

    def place_order(self, **order_params: Any) -> Dict[str, Any]:
        """
        Place an order on USDT-M Futures.

        Keyword arguments are forwarded directly to POST /fapi/v1/order.
        Expected keys: symbol, side, type, quantity, [price, timeInForce, stopPrice].
        """
        logger.info("Placing order | params: %s", _redact(order_params))
        result = self._request("POST", "/fapi/v1/order", params=order_params, signed=True)
        logger.info("Order placed successfully | orderId=%s status=%s",
                    result.get("orderId"), result.get("status"))
        return result

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Query a single order by symbol and orderId."""
        params = {"symbol": symbol, "orderId": order_id}
        return self._request("GET", "/fapi/v1/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        params = {"symbol": symbol, "orderId": order_id}
        return self._request("DELETE", "/fapi/v1/order", params=params, signed=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _redact(params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *params* with sensitive fields masked."""
    sensitive = {"signature", "apiKey", "api_key"}
    return {k: ("***" if k in sensitive else v) for k, v in params.items()}

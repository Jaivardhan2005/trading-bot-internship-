"""
Unit tests for the Binance Futures Trading Bot.

Run with:  pytest tests/ -v
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from bot.validators import (
    validate_symbol, validate_side, validate_order_type,
    validate_quantity, validate_price, validate_all,
)
from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.orders import OrderManager, OrderResult


# ─────────────────────────────────────────────────────────────────────────────
# Validator tests
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateSymbol:
    def test_uppercase(self):
        assert validate_symbol("btcusdt") == "BTCUSDT"

    def test_strips_whitespace(self):
        assert validate_symbol("  ETHUSDT  ") == "ETHUSDT"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_symbol("")

    def test_special_chars_raise(self):
        with pytest.raises(ValueError, match="invalid characters"):
            validate_symbol("BTC/USDT")


class TestValidateSide:
    def test_buy(self):
        assert validate_side("buy") == "BUY"

    def test_sell(self):
        assert validate_side("SELL") == "SELL"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid side"):
            validate_side("LONG")


class TestValidateOrderType:
    def test_market(self):
        assert validate_order_type("market") == "MARKET"

    def test_limit(self):
        assert validate_order_type("LIMIT") == "LIMIT"

    def test_stop_market(self):
        assert validate_order_type("stop_market") == "STOP_MARKET"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid order type"):
            validate_order_type("TRAILING_STOP")


class TestValidateQuantity:
    def test_valid_decimal(self):
        assert validate_quantity("0.001") == Decimal("0.001")

    def test_valid_int(self):
        assert validate_quantity(5) == Decimal("5")

    def test_zero_raises(self):
        with pytest.raises(ValueError, match="greater than zero"):
            validate_quantity("0")

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="greater than zero"):
            validate_quantity("-1")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="not a valid number"):
            validate_quantity("abc")


class TestValidatePrice:
    def test_price_required_for_limit(self):
        with pytest.raises(ValueError, match="required for LIMIT"):
            validate_price(None, "LIMIT")

    def test_price_required_for_stop_market(self):
        with pytest.raises(ValueError, match="required for STOP_MARKET"):
            validate_price(None, "STOP_MARKET")

    def test_price_not_required_for_market(self):
        assert validate_price(None, "MARKET") is None

    def test_valid_price(self):
        assert validate_price("95000", "LIMIT") == Decimal("95000")

    def test_zero_price_raises(self):
        with pytest.raises(ValueError, match="greater than zero"):
            validate_price("0", "LIMIT")


class TestValidateAll:
    def test_valid_market_order(self):
        result = validate_all("BTCUSDT", "BUY", "MARKET", "0.001")
        assert result["symbol"] == "BTCUSDT"
        assert result["side"] == "BUY"
        assert result["order_type"] == "MARKET"
        assert result["quantity"] == Decimal("0.001")
        assert result["price"] is None

    def test_valid_limit_order(self):
        result = validate_all("ETHUSDT", "SELL", "LIMIT", "0.1", "3000")
        assert result["price"] == Decimal("3000")

    def test_limit_without_price_raises(self):
        with pytest.raises(ValueError):
            validate_all("BTCUSDT", "BUY", "LIMIT", "0.001")


# ─────────────────────────────────────────────────────────────────────────────
# Client tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBinanceFuturesClient:
    def test_missing_credentials_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            BinanceFuturesClient(api_key="", api_secret="secret")

    def test_sign_produces_consistent_hex(self):
        client = BinanceFuturesClient("key", "secret")
        sig1 = client._sign({"symbol": "BTCUSDT", "timestamp": 12345})
        sig2 = client._sign({"symbol": "BTCUSDT", "timestamp": 12345})
        assert sig1 == sig2
        assert len(sig1) == 64  # SHA-256 hex digest length

    def test_build_signed_params_adds_timestamp_and_signature(self):
        client = BinanceFuturesClient("key", "secret")
        params = {"symbol": "BTCUSDT"}
        result = client._build_signed_params(params)
        assert "timestamp" in result
        assert "signature" in result

    @patch("bot.client.requests.Session.request")
    def test_request_raises_on_api_error(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"code": -1102, "msg": "Mandatory parameter missing."}
        mock_request.return_value = mock_resp

        client = BinanceFuturesClient("key", "secret")
        with pytest.raises(BinanceAPIError) as exc_info:
            client._request("GET", "/fapi/v1/exchangeInfo")
        assert exc_info.value.code == -1102

    @patch("bot.client.requests.Session.request")
    def test_place_order_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "orderId": 123456,
            "status": "FILLED",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.001",
            "executedQty": "0.001",
            "avgPrice": "100000",
            "clientOrderId": "test_order",
        }
        mock_request.return_value = mock_resp

        client = BinanceFuturesClient("key", "secret")
        result = client.place_order(symbol="BTCUSDT", side="BUY", type="MARKET", quantity="0.001")
        assert result["orderId"] == 123456
        assert result["status"] == "FILLED"


# ─────────────────────────────────────────────────────────────────────────────
# OrderManager tests
# ─────────────────────────────────────────────────────────────────────────────


class TestOrderManager:
    def _mock_client(self, response: dict) -> MagicMock:
        client = MagicMock()
        client.place_order.return_value = response
        return client

    def test_place_market_order_success(self):
        raw = {
            "orderId": 111, "status": "FILLED", "symbol": "BTCUSDT",
            "side": "BUY", "type": "MARKET", "origQty": "0.001",
            "executedQty": "0.001", "avgPrice": "100000",
            "clientOrderId": "abc",
        }
        manager = OrderManager(self._mock_client(raw))
        result = manager.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))

        assert result.success is True
        assert result.order_id == 111
        assert result.status == "FILLED"
        assert result.executed_qty == "0.001"

    def test_place_limit_order_success(self):
        raw = {
            "orderId": 222, "status": "NEW", "symbol": "BTCUSDT",
            "side": "SELL", "type": "LIMIT", "origQty": "0.001",
            "executedQty": "0.000", "avgPrice": "0", "price": "110000",
            "timeInForce": "GTC", "clientOrderId": "def",
        }
        manager = OrderManager(self._mock_client(raw))
        result = manager.place_limit_order("BTCUSDT", "SELL", Decimal("0.001"), Decimal("110000"))

        assert result.success is True
        assert result.order_id == 222
        assert result.status == "NEW"
        assert result.price == "110000"

    def test_place_order_api_error_returns_failure(self):
        client = MagicMock()
        client.place_order.side_effect = BinanceAPIError(-2019, "Margin is insufficient.")

        manager = OrderManager(client)
        result = manager.place_market_order("BTCUSDT", "BUY", Decimal("100"))

        assert result.success is False
        assert "Margin is insufficient" in result.error_message

    def test_place_order_network_error_returns_failure(self):
        client = MagicMock()
        client.place_order.side_effect = BinanceNetworkError("Connection refused")

        manager = OrderManager(client)
        result = manager.place_market_order("BTCUSDT", "BUY", Decimal("0.001"))

        assert result.success is False
        assert "Connection refused" in result.error_message


class TestOrderResult:
    def test_pretty_success(self):
        result = OrderResult(
            success=True, order_id=999, symbol="BTCUSDT", side="BUY",
            order_type="MARKET", status="FILLED", orig_qty="0.001",
            executed_qty="0.001", avg_price="100000",
            client_order_id="abc123",
        )
        pretty = result.pretty()
        assert "Order placed successfully" in pretty
        assert "999" in pretty
        assert "FILLED" in pretty
        assert "100000" in pretty

    def test_pretty_failure(self):
        result = OrderResult(success=False, error_message="Network timeout")
        assert "FAILED" in result.pretty()
        assert "Network timeout" in result.pretty()

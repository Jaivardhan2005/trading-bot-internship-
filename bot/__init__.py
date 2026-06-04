"""
trading_bot.bot — Binance Futures trading bot library.
"""

from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.orders import OrderManager, OrderResult
from bot.validators import validate_all

__all__ = [
    "BinanceFuturesClient",
    "BinanceAPIError",
    "BinanceNetworkError",
    "OrderManager",
    "OrderResult",
    "validate_all",
]

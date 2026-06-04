#!/usr/bin/env python3
"""
cli.py — Command-line entry point for the Binance Futures Trading Bot.

Usage examples:
  python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
  python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 95000
  python cli.py place-order --symbol ETHUSDT --side BUY --type STOP_MARKET --quantity 0.01 --price 3000
  python cli.py account
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from typing import Optional

import click
from dotenv import load_dotenv

from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.logging_config import setup_logging, get_logger
from bot.orders import OrderManager
from bot.validators import validate_all, VALID_SIDES, VALID_ORDER_TYPES

# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────────────────────────────────────

load_dotenv()
setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

TESTNET_URL = "https://testnet.binancefuture.com"

BANNER = r"""
╔══════════════════════════════════════════════╗
║   Binance Futures Testnet Trading Bot  v1.0  ║
║   USDT-M Perpetuals | Testnet Mode           ║
╚══════════════════════════════════════════════╝
"""


# ─────────────────────────────────────────────────────────────────────────────
# Shared context / helpers
# ─────────────────────────────────────────────────────────────────────────────


def _get_client() -> BinanceFuturesClient:
    """Build the API client from env vars, with clear error messages."""
    api_key    = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        click.echo(
            click.style(
                "\n  ERROR: BINANCE_API_KEY and BINANCE_API_SECRET must be set.\n"
                "  Copy .env.example → .env and fill in your testnet credentials.\n",
                fg="red",
            )
        )
        sys.exit(1)

    base_url = os.getenv("BINANCE_BASE_URL", TESTNET_URL)
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret, base_url=base_url)


def _print_section(title: str) -> None:
    click.echo(click.style(f"\n  ── {title} ", fg="cyan") + click.style("─" * max(0, 44 - len(title)), fg="cyan"))


def _exit_error(msg: str, code: int = 1) -> None:
    click.echo(click.style(f"\n  ✗  {msg}\n", fg="red"))
    logger.error(msg)
    sys.exit(code)


# ─────────────────────────────────────────────────────────────────────────────
# CLI group
# ─────────────────────────────────────────────────────────────────────────────


@click.group()
def cli() -> None:
    """Binance Futures Testnet Trading Bot — place and manage orders via CLI."""
    click.echo(click.style(BANNER, fg="yellow"))


# ─────────────────────────────────────────────────────────────────────────────
# place-order command
# ─────────────────────────────────────────────────────────────────────────────


@cli.command("place-order")
@click.option(
    "--symbol", "-s",
    required=True,
    help="Trading pair symbol, e.g. BTCUSDT.",
    metavar="SYMBOL",
)
@click.option(
    "--side",
    required=True,
    type=click.Choice(list(VALID_SIDES), case_sensitive=False),
    help="Order side: BUY or SELL.",
)
@click.option(
    "--type", "order_type",
    required=True,
    type=click.Choice(list(VALID_ORDER_TYPES), case_sensitive=False),
    help="Order type: MARKET, LIMIT, or STOP_MARKET.",
)
@click.option(
    "--quantity", "-q",
    required=True,
    type=str,
    help="Order quantity (e.g. 0.001 for BTC).",
    metavar="QTY",
)
@click.option(
    "--price", "-p",
    default=None,
    type=str,
    help="Price for LIMIT / stop price for STOP_MARKET orders.",
    metavar="PRICE",
)
@click.option(
    "--tif",
    default="GTC",
    type=click.Choice(["GTC", "IOC", "FOK"], case_sensitive=False),
    help="Time-in-Force for LIMIT orders (default: GTC).",
    show_default=True,
)
def place_order(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: Optional[str],
    tif: str,
) -> None:
    """
    Place a futures order on Binance Testnet.

    \b
    Examples:
      Market BUY:
        python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

      Limit SELL:
        python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 95000

      Stop-Market BUY (bonus):
        python cli.py place-order --symbol ETHUSDT --side BUY --type STOP_MARKET --quantity 0.01 --price 3000
    """
    # ── 1. Validate inputs ───────────────────────────────────────────────────
    _print_section("Order Request")
    try:
        validated = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
    except ValueError as exc:
        _exit_error(f"Validation error: {exc}")

    click.echo(f"  Symbol      : {validated['symbol']}")
    click.echo(f"  Side        : {validated['side']}")
    click.echo(f"  Order Type  : {validated['order_type']}")
    click.echo(f"  Quantity    : {validated['quantity']}")
    if validated["price"] is not None:
        click.echo(f"  Price       : {validated['price']}")
    if validated["order_type"] == "LIMIT":
        click.echo(f"  TIF         : {tif.upper()}")

    logger.info(
        "CLI place-order | symbol=%s side=%s type=%s qty=%s price=%s",
        validated["symbol"], validated["side"], validated["order_type"],
        validated["quantity"], validated["price"],
    )

    # ── 2. Build client & order manager ─────────────────────────────────────
    client = _get_client()
    manager = OrderManager(client)

    # ── 3. Route to the right order method ──────────────────────────────────
    _print_section("Sending to Binance Testnet")
    try:
        ot = validated["order_type"]
        if ot == "MARKET":
            result = manager.place_market_order(
                symbol=validated["symbol"],
                side=validated["side"],
                quantity=validated["quantity"],
            )
        elif ot == "LIMIT":
            result = manager.place_limit_order(
                symbol=validated["symbol"],
                side=validated["side"],
                quantity=validated["quantity"],
                price=validated["price"],
                time_in_force=tif.upper(),
            )
        elif ot == "STOP_MARKET":
            result = manager.place_stop_market_order(
                symbol=validated["symbol"],
                side=validated["side"],
                quantity=validated["quantity"],
                stop_price=validated["price"],
            )
        else:
            _exit_error(f"Unsupported order type: {ot}")

    except BinanceAPIError as exc:
        _exit_error(f"Binance API error ({exc.code}): {exc.message}")
    except BinanceNetworkError as exc:
        _exit_error(f"Network error: {exc}")
    except Exception as exc:
        logger.exception("Unexpected error during order placement")
        _exit_error(f"Unexpected error: {exc}")

    # ── 4. Print result ──────────────────────────────────────────────────────
    _print_section("Order Response")
    click.echo(result.pretty())

    if not result.success:
        sys.exit(1)

    _print_section("Raw API Response")
    click.echo("  " + json.dumps(result.raw_response, indent=4).replace("\n", "\n  "))
    click.echo()


# ─────────────────────────────────────────────────────────────────────────────
# account command
# ─────────────────────────────────────────────────────────────────────────────


@cli.command("account")
@click.option("--full", is_flag=True, default=False, help="Show full JSON response.")
def account(full: bool) -> None:
    """Display testnet account balance summary."""
    _print_section("Account Info")
    client = _get_client()

    try:
        data = client.get_account()
    except BinanceAPIError as exc:
        _exit_error(f"Binance API error ({exc.code}): {exc.message}")
    except BinanceNetworkError as exc:
        _exit_error(f"Network error: {exc}")

    if full:
        click.echo(json.dumps(data, indent=2))
        return

    # Show a condensed wallet summary
    assets = [a for a in data.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
    if not assets:
        click.echo("  No assets with non-zero balance found.")
    else:
        click.echo(f"  {'Asset':<8}  {'Wallet Balance':>18}  {'Unrealised PnL':>16}")
        click.echo(f"  {'─'*7:<8}  {'─'*18:>18}  {'─'*16:>16}")
        for a in assets:
            click.echo(
                f"  {a['asset']:<8}  {float(a['walletBalance']):>18.6f}"
                f"  {float(a.get('unrealizedProfit', 0)):>+16.6f}"
            )
    click.echo()


# ─────────────────────────────────────────────────────────────────────────────
# ping command
# ─────────────────────────────────────────────────────────────────────────────


@cli.command("ping")
def ping() -> None:
    """Check connectivity to the Binance Futures Testnet."""
    import requests as req
    url = f"{os.getenv('BINANCE_BASE_URL', TESTNET_URL)}/fapi/v1/ping"
    try:
        r = req.get(url, timeout=5)
        if r.status_code == 200:
            click.echo(click.style("  ✓  Testnet is reachable.", fg="green"))
        else:
            click.echo(click.style(f"  ✗  HTTP {r.status_code} from testnet.", fg="red"))
    except Exception as exc:
        click.echo(click.style(f"  ✗  Could not reach testnet: {exc}", fg="red"))
    click.echo()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    cli()

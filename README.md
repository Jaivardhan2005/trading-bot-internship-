# Binance Futures Testnet Trading Bot

A clean, production-style Python CLI application for placing orders on the **Binance USDT-M Futures Testnet**.  
Designed with a clear separation between the API/client layer and the CLI layer.

---

## Features

- **Market, Limit, and Stop-Market orders** (BUY / SELL)
- **Input validation** with clear error messages before any API call is made
- **Structured logging** — DEBUG detail to file, INFO to console, with rotating log files
- **Robust error handling** — API errors, network failures, and invalid input are all caught gracefully
- **Clean architecture** — `client.py` (transport) → `orders.py` (domain logic) → `cli.py` (presentation)

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Public re-exports
│   ├── client.py            # Binance REST client (HMAC signing, HTTP transport)
│   ├── orders.py            # Order placement logic & OrderResult model
│   ├── validators.py        # Input validation (pure functions, no side-effects)
│   └── logging_config.py   # Structured logging setup
├── tests/
│   └── test_bot.py          # Unit tests (validators, client, orders)
├── logs/
│   └── trading_bot.log      # Rotating log file (auto-created)
├── cli.py                   # CLI entry point (Click-based)
├── .env.example             # Environment variable template
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Register on Binance Futures Testnet

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Click **"Register Now"** and create an account
3. Go to **"API Key"** → generate a new key pair
4. Copy your **API Key** and **API Secret** — you'll need them below

### 2. Clone and install

```bash
git clone https://github.com/yourusername/trading-bot.git
cd trading-bot

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
.venv\Scripts\activate             # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your testnet credentials:

```ini
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
BINANCE_BASE_URL=https://testnet.binancefuture.com   # default — no change needed
LOG_LEVEL=INFO                                        # or DEBUG for verbose logging
```

---

## How to Run

### Check connectivity

```bash
python cli.py ping
```

### Place a Market BUY order

```bash
python cli.py place-order \
  --symbol BTCUSDT \
  --side   BUY \
  --type   MARKET \
  --quantity 0.001
```

Expected output:
```
  ── Order Request ─────────────────────────────────────
  Symbol      : BTCUSDT
  Side        : BUY
  Order Type  : MARKET
  Quantity    : 0.001

  ── Sending to Binance Testnet ────────────────────────

  ── Order Response ────────────────────────────────────
  ✓  Order placed successfully
     Order ID      : 4082931847
     Client Ord ID : web_abc123XYZ
     Symbol        : BTCUSDT
     Side          : BUY
     Type          : MARKET
     Status        : FILLED
     Orig Qty      : 0.001
     Executed Qty  : 0.001
     Avg Price     : 103427.20
```

---

### Place a Limit SELL order

```bash
python cli.py place-order \
  --symbol BTCUSDT \
  --side   SELL \
  --type   LIMIT \
  --quantity 0.001 \
  --price  108000
```

For IOC or FOK fill policy:

```bash
python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT \
  --quantity 0.001 --price 108000 --tif IOC
```

---

### Place a Stop-Market order (bonus feature)

```bash
python cli.py place-order \
  --symbol   ETHUSDT \
  --side     BUY \
  --type     STOP_MARKET \
  --quantity 0.01 \
  --price    3800           # used as the stop trigger price
```

---

### View account balances

```bash
python cli.py account          # concise summary
python cli.py account --full   # full JSON response
```

---

### Help

```bash
python cli.py --help
python cli.py place-order --help
```

---

## Running Tests

```bash
pytest tests/ -v
```

All tests use mocks — no real API calls or credentials required.

---

## Logging

Logs are written to **`logs/trading_bot.log`** (auto-created).

| Level   | Console | Log file |
|---------|---------|----------|
| DEBUG   | —       | ✓        |
| INFO    | ✓       | ✓        |
| WARNING | ✓       | ✓        |
| ERROR   | ✓       | ✓        |

Each log line format:
```
2025-06-04 10:12:02 | INFO     | bot.orders | MARKET order request | symbol=BTCUSDT side=BUY qty=0.001
```

Log files rotate at 10 MB with up to 5 backups. API signatures are redacted in logs.

---

## Assumptions

- **Testnet only** — the `BINANCE_BASE_URL` defaults to `https://testnet.binancefuture.com`. Change it to the production URL at your own risk.
- **Quantity precision** — the bot passes your quantity string directly to the API. If the API rejects it with a precision error (`-1111`), round your quantity to the symbol's allowed step size (visible in Exchange Info).
- **Stop-Market price** — the `--price` flag doubles as the `stopPrice` for `STOP_MARKET` orders.
- **No position management** — the bot only places orders; it does not track positions, PnL, or manage risk.
- **Python 3.10+** recommended (uses `match` in `.env.example` comments; the code itself is 3.8+ compatible).

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing `--price` for LIMIT order | Validation error before any API call |
| Invalid symbol characters | Validation error |
| Binance API error (e.g. insufficient margin) | Clear message with error code |
| Network timeout / connection refused | Friendly network error message |
| Non-JSON response | Caught and reported |

All errors are logged to file with full stack traces at DEBUG level.

---

## License

MIT

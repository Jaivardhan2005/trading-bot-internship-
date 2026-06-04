"""
Logging configuration for the Binance Futures Trading Bot.
Sets up structured logging to both console and rotating file handler.
"""

import logging
import logging.handlers
import os
from pathlib import Path


LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "trading_bot.log"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(log_level: str = "INFO", log_file: Path = LOG_FILE) -> None:
    """
    Configure root logger with a console handler and a rotating file handler.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file:  Path to the log file. Parent directories are created automatically.
    """
    global _configured
    if _configured:
        return

    log_file.parent.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)          # capture everything at root level

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Console handler ──────────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # ── Rotating file handler (10 MB × 5 backups) ────────────────────────────
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)         # always write DEBUG to file
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).debug(
        "Logging initialised — file: %s, console level: %s", log_file, log_level
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (call setup_logging first)."""
    return logging.getLogger(name)

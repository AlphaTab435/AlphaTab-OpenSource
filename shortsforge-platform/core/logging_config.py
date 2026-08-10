"""
ShortsForge — Logging Configuration
Consistent logging across all modules.
Per TECHNICAL_ADDENDUM §2: RotatingFileHandler + console output.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir: str = "data/logs", level: str = None):
    """
    Configures root logger with console + rotating file output.
    
    Call this ONCE at application startup (pipeline.py, runner.py, etc.).
    
    Args:
        log_dir: Directory for log files (created if missing).
        level: Override log level. Defaults to DEBUG in DEV_MODE, INFO in production.
    """
    from core.config import DEV_MODE
    
    # Determine log level
    if level:
        log_level = getattr(logging, level.upper(), logging.INFO)
    else:
        log_level = logging.DEBUG if DEV_MODE else logging.INFO

    # Create log directory if missing
    os.makedirs(log_dir, exist_ok=True)

    # Log format
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=date_fmt)

    # Console handler — always INFO+ to keep terminal clean
    # (file handler gets full DEBUG if DEV_MODE)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # File handler (rotating, max 5 MB, keep 3 backups)
    log_file = os.path.join(log_dir, "shortsforge.log")
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates on re-init
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy_logger in [
        "httpx", "httpcore", "google", "gtts", "gtts.tts", "gtts.lang",
        "urllib3", "urllib3.connectionpool", "aiohttp", "aiosqlite",
        "uvicorn.access",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    mode_label = "DEV" if DEV_MODE else "PRODUCTION"
    logging.getLogger(__name__).info(
        f"Logging initialized [{mode_label}] level={logging.getLevelName(log_level)} -> {log_file}"
    )

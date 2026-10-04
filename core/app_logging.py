"""
core/app_logging.py — Rotating file logger for Assistant Worker.

Import this early in main.py before any other module so every subsequent
logger.getLogger() call picks up the handler.

Log location:  %LOCALAPPDATA%\\AssistantWorker\\logs\\assistant_worker.log
Max size:      5 MB per file, keep 3 backups → 15 MB total cap
"""
from __future__ import annotations

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class SecretSanitizingFilter(logging.Filter):
    """Redacts potential API keys, bearer tokens, and secrets from log records."""
    _PATTERN = re.compile(
        r'(AIza[0-9A-Za-z\-_]{35}|sk-[0-9A-Za-z]{20,}|Bearer\s+[0-9A-Za-z\-_.]+|key=[\'"][^\'"]+[\'"])',
        re.IGNORECASE,
    )

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._PATTERN.sub("[REDACTED]", record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (self._PATTERN.sub("[REDACTED]", str(v)) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    (self._PATTERN.sub("[REDACTED]", str(v)) if isinstance(v, str) else v)
                    for v in record.args
                )
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure root logger with a rotating file handler and (in dev) a console
    handler.  Safe to call multiple times — handlers are only added once.
    Returns the root logger.
    """
    # Import here to avoid circular-import if paths itself logs something
    from core.paths import LOGS_DIR

    log_file = LOGS_DIR / "assistant_worker.log"

    root = logging.getLogger()
    if root.handlers:
        return root  # already configured

    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler — never fills the disk
    fh = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,   # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.addFilter(SecretSanitizingFilter())
    root.addHandler(fh)

    # Console handler only in development (no console in frozen windowed build)
    if not getattr(sys, "frozen", False):
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        ch.addFilter(SecretSanitizingFilter())
        root.addHandler(ch)

    root.info("=== Assistant Worker logging started ===")
    return root


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — call setup_logging() first."""
    return logging.getLogger(name)

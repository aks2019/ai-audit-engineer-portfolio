from __future__ import annotations

import logging
from typing import Optional

from loguru import logger as _loguru_logger


class InterceptHandler(logging.Handler):
    """Redirect standard logging records to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging to go through loguru."""

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    _loguru_logger.remove()
    _loguru_logger.add(
        sink=lambda msg: print(msg, end=""),
        level=level,
        backtrace=False,
        diagnose=False,
    )


def get_logger(name: Optional[str] = None):
    """Return a loguru logger with optional contextual name."""

    if not _loguru_logger._core.handlers:
        configure_logging()

    return _loguru_logger.bind(logger=name or "audit-anomaly-detector")


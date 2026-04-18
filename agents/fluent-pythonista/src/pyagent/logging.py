"""Structured logging configuration for PyAgent."""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger for the application.

    Call once at the application entry point. All modules should obtain
    their logger via ``get_logger(__name__)``.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    root = logging.getLogger("pyagent")
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    """Return a logger scoped under the ``pyagent`` namespace.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    return logging.getLogger(f"pyagent.{name}")

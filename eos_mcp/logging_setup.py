"""Logging configuration.

Everything this package emits goes to **stderr**. Under the stdio transport the
MCP client parses stdout as a stream of JSON-RPC frames, so a stray write there
corrupts the protocol. Never use ``print()`` anywhere in this package -
``tests/test_no_stdout.py`` enforces that.
"""

from __future__ import annotations

import logging
import sys

from .config import config

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_configured = False


def configure_logging(level: str | None = None) -> None:
    """Install a stderr log handler for the ``eos_mcp`` logger tree.

    Safe to call more than once; only the first call installs a handler.

    Args:
        level: Overrides ``EOS_LOG_LEVEL``. Used by tests.
    """
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    logger = logging.getLogger("eos_mcp")
    logger.setLevel(level or config.log_level)
    logger.addHandler(handler)
    # Don't let records reach a root handler that may be attached to stdout.
    logger.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger under the ``eos_mcp`` tree."""
    return logging.getLogger(name)

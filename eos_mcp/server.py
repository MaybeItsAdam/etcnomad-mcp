"""Server entry point: configure logging, start the listener, serve MCP."""

from __future__ import annotations

from .app import mcp
from .config import config
from .logging_setup import configure_logging, get_logger
from .osc.listener import listener

logger = get_logger(__name__)


def run() -> None:
    """Start the OSC listener and run the MCP server on stdio.

    A listener that fails to bind does not stop the server: command tools still
    work, and `get_connection_health` reports the reason queries have no data.
    """
    configure_logging()

    # Importing these registers their @mcp.tool() / @mcp.prompt() decorators.
    from . import prompts, tools  # noqa: F401

    logger.info(
        "Starting ETC Eos MCP server (commands to %s, listening on %s)",
        config.tx_target,
        config.rx_target,
    )

    if not listener.start():
        logger.warning("Continuing without an OSC listener; queries will report no data.")

    try:
        mcp.run()
    finally:
        listener.stop()


if __name__ == "__main__":
    run()

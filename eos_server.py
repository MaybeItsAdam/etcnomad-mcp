"""Entry point shim for the ETC Eos MCP server.

The implementation lives in the ``eos_mcp`` package. This preserves the
documented ``uv run eos_server.py`` launch command; installing the package also
provides an ``eos-mcp`` console script that does the same thing.
"""

from eos_mcp.server import run

if __name__ == "__main__":
    run()

"""Hardkeys, softkeys, and macros."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..app import mcp
from ..osc import address as addr
from ._common import TargetNumber, ToolResult, guarded, press, send


@mcp.tool()
@guarded("press_key")
def press_key(key_name: str) -> ToolResult:
    """Presses and releases a console hardkey.

    Args:
        key_name: The Eos key name, e.g. "Data", "About", "go_0", "stop",
            "live", "blind". Letters, digits and underscores only.
    """
    key = addr.segment(key_name, "key_name")
    return press(f"/eos/key/{key}", action="press_key", detail=f"Pressed key {key}")


@mcp.tool()
@guarded("fire_macro")
def fire_macro(macro: TargetNumber) -> ToolResult:
    """Fires a macro."""
    return send("/eos/macro/fire", macro, action="fire_macro", detail=f"Fired macro {macro}")


@mcp.tool()
@guarded("press_softkey")
def press_softkey(index: Annotated[int, Field(ge=1, le=12)]) -> ToolResult:
    """Presses a softkey.

    Args:
        index: Softkey position, 1-12.
    """
    return press(f"/eos/softkey/{index}", action="press_softkey", detail=f"Pressed softkey {index}")

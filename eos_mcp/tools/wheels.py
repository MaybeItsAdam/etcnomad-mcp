"""Encoder wheels."""

from __future__ import annotations

from ..app import mcp
from ..osc import address as addr
from ._common import ToolResult, guarded, send


@mcp.tool()
@guarded("wheel_level")
def wheel_level(ticks: float) -> ToolResult:
    """Nudges the intensity wheel.

    Args:
        ticks: Number of ticks. Positive raises, negative lowers.
    """
    return send(
        "/eos/wheel/level", ticks, action="wheel_level", detail=f"Moved level wheel {ticks} ticks"
    )


@mcp.tool()
@guarded("wheel_parameter")
def wheel_parameter(param: str, ticks: float) -> ToolResult:
    """Nudges the encoder for a named parameter.

    Args:
        param: Parameter name, e.g. "pan", "tilt", "zoom".
        ticks: Number of ticks. Positive and negative both valid.
    """
    name = addr.segment(param, "param")
    return send(
        f"/eos/wheel/{name}",
        ticks,
        action="wheel_parameter",
        detail=f"Moved {name} wheel {ticks} ticks",
    )


@mcp.tool()
@guarded("switch_parameter")
def switch_parameter(param: str, ticks: float) -> ToolResult:
    """Sets a parameter's switch (repeat) rate.

    Args:
        param: Parameter name.
        ticks: Tick rate.
    """
    name = addr.segment(param, "param")
    return send(
        f"/eos/switch/{name}",
        ticks,
        action="switch_parameter",
        detail=f"Set switch {name} to {ticks}",
    )

"""Command line, intensity levels, parameters, and raw DMX output."""

from __future__ import annotations

from typing import Literal

from ..app import mcp
from ..errors import EosValidationError
from ..osc import address as addr
from ._common import (
    DmxValue,
    LevelModifier,
    ParamModifier,
    Percent,
    TargetNumber,
    ToolResult,
    guarded,
    send,
)


@mcp.tool()
@guarded("command_line")
def command_line(command: str) -> ToolResult:
    """Types a command into the Eos command line and executes it.

    This is the most powerful tool available - it can express anything the
    console can do, including record and delete operations. Prefer a specific
    tool when one exists.

    Args:
        command: The command string, e.g. "Chan 1 At 50" or "Chan 1 Thru 10 Out".
    """
    text = command.strip()
    if not text:
        raise EosValidationError("command must not be empty")
    return send("/eos/cmd", text, action="command_line", detail=f"Sent command: {text}")


@mcp.tool()
@guarded("set_level")
def set_level(value: Percent) -> ToolResult:
    """Sets the intensity of the currently selected channels.

    Args:
        value: Intensity percentage, 0-100.
    """
    return send("/eos/at", value, action="set_level", detail=f"Set level to {value}")


@mcp.tool()
@guarded("apply_modifier")
def apply_modifier(
    modifier: LevelModifier,
    target: Literal["selection", "channel", "group"] = "selection",
    number: TargetNumber | None = None,
) -> ToolResult:
    """Applies an intensity modifier to the current selection, a channel, or a group.

    Args:
        modifier: The modifier to apply, e.g. "full", "out", "home".
        target: What to apply it to. "selection" uses whatever is currently
            selected; "channel" and "group" require `number`.
        number: Channel or group number. Required unless target is "selection".
    """
    mod = addr.segment(modifier, "modifier")

    if target == "selection":
        if number is not None:
            raise EosValidationError("number must be omitted when target is 'selection'")
        return send(
            f"/eos/at/{mod}",
            action="apply_modifier",
            detail=f"Applied '{modifier}' to the current selection",
        )

    if number is None:
        raise EosValidationError(f"number is required when target is '{target}'")

    prefix = "chan" if target == "channel" else "group"
    return send(
        f"/eos/{prefix}/{number}/{mod}",
        action="apply_modifier",
        detail=f"Applied '{modifier}' to {target} {number}",
    )


@mcp.tool()
@guarded("set_parameter")
def set_parameter(param: str, value: float) -> ToolResult:
    """Sets a named parameter on the current selection to a value.

    Args:
        param: Parameter name, e.g. "pan", "tilt", "zoom", "edge".
        value: Value to set, in the parameter's own units.
    """
    name = addr.segment(param, "param")
    return send(
        f"/eos/param/{name}",
        value,
        action="set_parameter",
        detail=f"Set {name} to {value}",
    )


@mcp.tool()
@guarded("set_parameter_mod")
def set_parameter_mod(param: str, modification: ParamModifier) -> ToolResult:
    """Applies a modifier to a named parameter on the current selection.

    Args:
        param: Parameter name, e.g. "pan", "zoom".
        modification: The modifier to apply, e.g. "home", "full".
    """
    name = addr.segment(param, "param")
    mod = addr.segment(modification, "modification")
    return send(
        f"/eos/param/{name}/{mod}",
        action="set_parameter_mod",
        detail=f"Applied '{modification}' to {name}",
    )


@mcp.tool()
@guarded("set_dmx")
def set_dmx(address_num: TargetNumber, value: DmxValue) -> ToolResult:
    """Sets a raw DMX address to an 8-bit level, bypassing channel patching.

    Args:
        address_num: 1-based DMX address.
        value: Output level, 0-255.
    """
    return send(
        f"/eos/addr/{address_num}/DMX",
        value,
        action="set_dmx",
        detail=f"Set DMX address {address_num} to {value}",
    )

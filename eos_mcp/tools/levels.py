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
def command_line(command: str, reset: bool = True) -> ToolResult:
    """Types a command into the Eos command line.

    This is the most powerful tool available - it can express anything the
    console can do, including record and delete operations. Prefer a specific
    tool when one exists.

    The command is only *executed* if it is terminated, either by ending it
    with "Enter" or with "#". An unterminated command is left pending on the
    command line, exactly as if it had been typed but not confirmed.

    Args:
        command: The command string, e.g. "Chan 1 At 50 Enter".
        reset: Clear whatever is already on the command line first (the
            default). Eos otherwise *appends*, so a leftover fragment silently
            turns the next command into a syntax error - or worse, into a
            different valid command. Pass ``False`` only to deliberately build
            a command up across several calls.
    """
    text = command.strip()
    if not text:
        raise EosValidationError("command must not be empty")
    address = "/eos/newcmd" if reset else "/eos/cmd"
    how = "Sent command" if reset else "Appended to command line"
    return send(address, text, action="command_line", detail=f"{how}: {text}")


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

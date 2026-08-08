"""Command line, intensity levels, parameters, and raw DMX output."""

from __future__ import annotations

import time
from typing import Literal

from ..app import mcp
from ..errors import EosValidationError
from ..osc import address as addr
from ..state import state, state_lock
from ._common import (
    DmxValue,
    LevelModifier,
    ParamModifier,
    Percent,
    TargetNumber,
    ToolResult,
    failure,
    guarded,
    send,
)

#: How long to wait for Eos to echo the command line back.
CONFIRM_TIMEOUT = 1.0
CONFIRM_POLL_INTERVAL = 0.05

#: What Eos appends when holding a destructive command for confirmation.
CONFIRM_PROMPT = "Please Confirm"


def _context_of(command_line_text: str) -> str:
    """Extract the display context from an Eos command line.

    Eos formats the line as ``<mode>: <context> : <command>`` - for example
    ``LIVE: Cue  0.1 : Chan 30 @ Full #`` or ``BLIND: Setup : ``. The middle
    segment is the display currently receiving keystrokes.
    """
    parts = command_line_text.split(":")
    return parts[1].strip() if len(parts) > 2 else ""


def _confirm(result: ToolResult, text: str, before_seq: int) -> ToolResult:
    """Read the command line back and report what the console made of it.

    A successful send only means the packet left this machine. Eos discards
    commands whose keystrokes belong to another display - Setup swallows them
    silently - reports syntax errors only on the command line, and holds
    destructive commands at a confirmation prompt. None of that is visible in
    the send result, so each would otherwise surface as ``ok: true`` with the
    show unchanged, which is the most expensive way for this tool to fail.

    Waiting on a sequence number rather than the text matters: re-sending an
    identical command produces an identical line, and comparing text would
    report a working command as unconfirmed.
    """
    deadline = time.monotonic() + CONFIRM_TIMEOUT
    readback = ""
    echoed = False
    while time.monotonic() < deadline:
        with state_lock:
            if state.command_line_seq != before_seq:
                readback = state.command_line
                echoed = True
                break
        time.sleep(CONFIRM_POLL_INTERVAL)

    result["console_command_line"] = readback

    if not echoed:
        result["confirmed"] = False
        result["detail"] += (
            f" NOT CONFIRMED: the console did not echo a command line within "
            f"{CONFIRM_TIMEOUT}s. Do not assume this took effect - check "
            "get_connection_health, and verify with list_show_targets if it wrote anything."
        )
        return result

    if "Error" in readback:
        return failure(
            "command_line",
            f"The console rejected {text!r}. Its command line reads: {readback}",
            console_command_line=readback,
            confirmed=True,
        )

    context = _context_of(readback)
    result["console_context"] = context

    if CONFIRM_PROMPT in readback:
        # Eos guards destructive commands this way. Nothing has happened yet,
        # and reporting success here would be reporting a delete that did not
        # occur - the worst direction for this to be wrong in.
        result["confirmed"] = False
        result["awaiting_confirmation"] = True
        result["detail"] += (
            f" NOT EXECUTED: the console is holding this at a confirmation prompt "
            f"({readback!r}). Send press_key('enter') to confirm, or "
            "press_key('clear_cmdline') to abandon it. Nothing has changed yet."
        )
        return result

    result["confirmed"] = True
    if context.startswith("Setup"):
        result["confirmed"] = False
        result["detail"] += (
            " NOT CONFIRMED: the console is in Setup, which consumes keystrokes, so this "
            "almost certainly did nothing. Leave Setup first - press_key('live') - and retry."
        )
    return result


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

    with state_lock:
        before_seq = state.command_line_seq

    result = send(address, text, action="command_line", detail=f"{how}: {text}")
    return _confirm(result, text, before_seq)


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

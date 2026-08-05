"""Faders and direct select buttons."""

from __future__ import annotations

from ..app import mcp
from ..osc import address as addr
from ._common import (
    BankIndex,
    FaderAction,
    Normalised,
    TargetNumber,
    ToolResult,
    guarded,
    press,
    send,
)


@mcp.tool()
@guarded("set_fader")
def set_fader(bank: BankIndex, fader: TargetNumber, level: Normalised) -> ToolResult:
    """Sets a fader to a level.

    Args:
        bank: Fader bank index, as configured on the console.
        fader: Fader index within the bank.
        level: Normalised level, 0.0 (out) to 1.0 (full).
    """
    return send(
        f"/eos/fader/{bank}/{fader}",
        level,
        action="set_fader",
        detail=f"Set fader {bank}/{fader} to {level}",
    )


@mcp.tool()
@guarded("control_fader_button")
def control_fader_button(bank: BankIndex, fader: TargetNumber, action: FaderAction) -> ToolResult:
    """Presses one of the buttons attached to a fader.

    Args:
        bank: Fader bank index.
        fader: Fader index within the bank.
        action: Which button to press.
    """
    verb = addr.segment(action, "action")
    return send(
        f"/eos/fader/{bank}/{fader}/{verb}",
        action="control_fader_button",
        detail=f"Fader {bank}/{fader}: {action}",
    )


@mcp.tool()
@guarded("press_direct_select")
def press_direct_select(bank: BankIndex, button: TargetNumber) -> ToolResult:
    """Presses a direct select button.

    Args:
        bank: Direct select bank index.
        button: Button index within the bank.
    """
    return press(
        f"/eos/ds/{bank}/{button}",
        action="press_direct_select",
        detail=f"Pressed direct select {bank}/{button}",
    )

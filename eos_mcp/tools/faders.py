"""Faders and direct select buttons."""

from __future__ import annotations

from typing import Literal

from ..app import mcp
from ..errors import EosValidationError
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

#: Target types a direct select bank can be filled with.
DirectSelectTarget = Literal[
    "chan",
    "group",
    "macro",
    "sub",
    "preset",
    "ip",
    "fp",
    "cp",
    "bp",
    "ms",
    "curve",
    "snap",
    "fx",
    "pixmap",
    "scene",
]


@mcp.tool()
@guarded("configure_fader_bank")
def configure_fader_bank(bank: TargetNumber, count: int, page: int | None = None) -> ToolResult:
    """Creates an OSC fader bank so its faders can be read and driven.

    Eos sends no fader labels or levels until a bank has been created, so
    ``get_faders`` returns nothing until this is called. OSC fader <bank>/<n>
    maps to the same console fader, so a bank of 10 gives access to console
    faders 1-10.

    Args:
        bank: 1-based OSC fader bank index. Use 0 for the master fader.
        count: How many faders the bank should have.
        page: Optional page to jump to when creating it.
    """
    if count < 1:
        raise EosValidationError("count must be at least 1")
    suffix = f"{page}/{count}" if page is not None else f"{count}"
    where = f" on page {page}" if page is not None else ""
    return send(
        f"/eos/fader/{bank}/config/{suffix}",
        action="configure_fader_bank",
        detail=f"Created OSC fader bank {bank} with {count} faders{where}",
    )


@mcp.tool()
@guarded("configure_direct_selects")
def configure_direct_selects(
    bank: TargetNumber,
    target_type: DirectSelectTarget,
    count: int,
    page: int | None = None,
    flexi: bool = False,
) -> ToolResult:
    """Creates an OSC direct select bank so its buttons can be read and pressed.

    As with fader banks, Eos sends no button labels until the bank exists, so
    ``get_direct_selects`` is empty until this is called.

    Args:
        bank: 1-based OSC direct select bank index.
        target_type: What the buttons address, e.g. "sub", "group", "fx".
        count: How many buttons the bank should have.
        page: Optional page to jump to when creating it.
        flexi: Create the bank in Flexi mode.
    """
    if count < 1:
        raise EosValidationError("count must be at least 1")
    parts = [f"/eos/ds/{bank}/{addr.segment(target_type, 'target_type')}"]
    if flexi:
        parts.append("flexi")
    if page is not None:
        parts.append(str(page))
    parts.append(str(count))
    return send(
        "/".join(parts),
        action="configure_direct_selects",
        detail=f"Created OSC direct select bank {bank} with {count} {target_type} buttons",
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

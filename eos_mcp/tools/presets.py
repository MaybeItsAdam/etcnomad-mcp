"""Presets, palettes, snapshots, and submasters."""

from __future__ import annotations

from ..app import mcp
from ._common import (
    Normalised,
    PaletteType,
    TargetNumber,
    ToolResult,
    guarded,
    send,
)

#: Eos OSC address stems for each palette type.
_PALETTE_STEMS = {"intensity": "ip", "focus": "fp", "color": "cp", "beam": "bp"}


@mcp.tool()
@guarded("fire_preset")
def fire_preset(preset: TargetNumber) -> ToolResult:
    """Recalls a preset onto the current selection."""
    return send("/eos/preset/fire", preset, action="fire_preset", detail=f"Fired preset {preset}")


@mcp.tool()
@guarded("fire_palette")
def fire_palette(palette_type: PaletteType, number: TargetNumber) -> ToolResult:
    """Recalls a palette onto the current selection.

    Args:
        palette_type: Which palette family to recall from.
        number: Palette number.
    """
    stem = _PALETTE_STEMS[palette_type]
    return send(
        f"/eos/{stem}/fire",
        number,
        action="fire_palette",
        detail=f"Fired {palette_type} palette {number}",
    )


@mcp.tool()
@guarded("recall_snapshot")
def recall_snapshot(snapshot: TargetNumber) -> ToolResult:
    """Recalls a snapshot, restoring a saved console layout/state."""
    return send(
        "/eos/snap", snapshot, action="recall_snapshot", detail=f"Recalled snapshot {snapshot}"
    )


@mcp.tool()
@guarded("bump_sub")
def bump_sub(sub: TargetNumber, level: Normalised = 1.0) -> ToolResult:
    """Bumps a submaster to a level.

    Args:
        sub: Submaster number.
        level: Normalised level, 0.0-1.0. Defaults to full.
    """
    return send(
        f"/eos/sub/{sub}/fire",
        level,
        action="bump_sub",
        detail=f"Bumped sub {sub} to {level}",
    )

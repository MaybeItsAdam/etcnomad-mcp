"""Cue playback: firing cues and driving the master playback pair."""

from __future__ import annotations

from ..app import mcp
from ..osc import address as addr
from ._common import TargetNumber, ToolResult, guarded, press, send


@mcp.tool()
@guarded("fire_cue")
def fire_cue(list_number: TargetNumber, cue_number: str) -> ToolResult:
    """Fires a specific cue immediately.

    Args:
        list_number: Cue list number.
        cue_number: Cue number. Point cues such as "1.5" are supported.
    """
    cue = addr.cue_number(cue_number)
    return send(
        f"/eos/cue/{list_number}/{cue}/fire",
        1.0,
        action="fire_cue",
        detail=f"Fired cue {cue} in list {list_number}",
    )


@mcp.tool()
@guarded("go_cue")
def go_cue() -> ToolResult:
    """Presses Go on the master playback pair, advancing to the next cue."""
    return press("/eos/key/go_0", action="go_cue", detail="Pressed Go")


@mcp.tool()
@guarded("stop_back_cue")
def stop_back_cue() -> ToolResult:
    """Presses Stop/Back: halts a running fade, or steps back if nothing is running."""
    return press("/eos/key/stop", action="stop_back_cue", detail="Pressed Stop/Back")


@mcp.tool()
@guarded("reset_osc")
def reset_osc() -> ToolResult:
    """Asks Eos to reset its OSC connection.

    Useful if the console has stopped sending updates. Follow it with
    `sync_state` to repopulate.
    """
    return send("/eos/reset", action="reset_osc", detail="Sent OSC reset")

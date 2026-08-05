"""Selecting channels, groups, and other console targets."""

from __future__ import annotations

from ..app import mcp
from ..osc import address as addr
from ._common import TargetNumber, ToolResult, guarded, send


@mcp.tool()
@guarded("select_channel")
def select_channel(channel: str) -> ToolResult:
    """Selects a channel or a range of channels.

    A plain number is sent directly. Anything else (a range such as
    "1 Thru 10", or a list such as "1+5+9") is routed through the command line,
    which is the only way Eos accepts a multi-channel selection over OSC.

    Args:
        channel: A channel number, or a range/list expression.
    """
    spec = addr.channel_spec(channel)
    if spec.isdigit():
        return send(
            "/eos/chan",
            int(spec),
            action="select_channel",
            detail=f"Selected channel {spec}",
        )
    return send(
        "/eos/cmd",
        f"Chan {spec}",
        action="select_channel",
        detail=f"Selected channels '{spec}' via the command line",
    )


@mcp.tool()
@guarded("select_group")
def select_group(group: TargetNumber) -> ToolResult:
    """Selects a group."""
    return send("/eos/group", group, action="select_group", detail=f"Selected group {group}")


@mcp.tool()
@guarded("select_address_target")
def select_address_target(address_num: TargetNumber) -> ToolResult:
    """Selects a DMX address as the current target."""
    return send(
        "/eos/addr",
        address_num,
        action="select_address_target",
        detail=f"Selected address {address_num}",
    )


@mcp.tool()
@guarded("select_curve")
def select_curve(curve: TargetNumber) -> ToolResult:
    """Selects a curve."""
    return send("/eos/curve", curve, action="select_curve", detail=f"Selected curve {curve}")


@mcp.tool()
@guarded("select_effect")
def select_effect(effect: TargetNumber) -> ToolResult:
    """Selects an effect."""
    return send("/eos/fx", effect, action="select_effect", detail=f"Selected effect {effect}")


@mcp.tool()
@guarded("select_pixel_map")
def select_pixel_map(pixmap: TargetNumber) -> ToolResult:
    """Selects a pixel map."""
    return send(
        "/eos/pixmap",
        pixmap,
        action="select_pixel_map",
        detail=f"Selected pixel map {pixmap}",
    )


@mcp.tool()
@guarded("open_magic_sheet")
def open_magic_sheet(ms: TargetNumber) -> ToolResult:
    """Opens a magic sheet."""
    return send("/eos/ms", ms, action="open_magic_sheet", detail=f"Opened magic sheet {ms}")

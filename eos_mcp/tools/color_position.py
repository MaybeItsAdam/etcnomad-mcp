"""Colour mixing and fixture positioning."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..app import mcp
from ._common import Normalised, Percent, ToolResult, guarded, send

Hue = Annotated[float, Field(ge=0, le=360, description="Hue in degrees, 0-360")]


@mcp.tool()
@guarded("set_xyz")
def set_xyz(x: float, y: float, z: float) -> ToolResult:
    """Sets the XYZ focus position of the current selection, in stage coordinates."""
    return send("/eos/xyz", [x, y, z], action="set_xyz", detail=f"Set XYZ to {x}, {y}, {z}")


@mcp.tool()
@guarded("set_color_hs")
def set_color_hs(hue: Hue, saturation: Percent) -> ToolResult:
    """Sets colour by hue and saturation.

    Args:
        hue: Hue in degrees, 0-360.
        saturation: Saturation percentage, 0-100.
    """
    return send(
        "/eos/color/hs",
        [hue, saturation],
        action="set_color_hs",
        detail=f"Set colour to hue {hue}, saturation {saturation}",
    )


@mcp.tool()
@guarded("set_color_rgb")
def set_color_rgb(red: Normalised, green: Normalised, blue: Normalised) -> ToolResult:
    """Sets colour by RGB.

    Args:
        red: Red component, 0.0-1.0.
        green: Green component, 0.0-1.0.
        blue: Blue component, 0.0-1.0.
    """
    return send(
        "/eos/color/rgb",
        [red, green, blue],
        action="set_color_rgb",
        detail=f"Set colour to RGB {red}, {green}, {blue}",
    )


@mcp.tool()
@guarded("set_color_xy")
def set_color_xy(x: Normalised, y: Normalised) -> ToolResult:
    """Sets colour by CIE xy chromaticity coordinates, each 0.0-1.0."""
    return send(
        "/eos/color/xy", [x, y], action="set_color_xy", detail=f"Set colour to CIE xy {x}, {y}"
    )


@mcp.tool()
@guarded("set_pan_tilt")
def set_pan_tilt(pan: float, tilt: float) -> ToolResult:
    """Sets pan and tilt on the current selection.

    Args:
        pan: Pan value. Normally 0.0-1.0, mapping across the fixture's range.
        tilt: Tilt value, on the same scale as pan.
    """
    return send(
        "/eos/pantilt/xy",
        [pan, tilt],
        action="set_pan_tilt",
        detail=f"Set pan/tilt to {pan}, {tilt}",
    )

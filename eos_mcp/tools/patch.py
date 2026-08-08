"""Patch metadata: labels, text fields, and gel.

Eos exposes ``/eos/set/patch/...`` for the descriptive fields of a patched
channel, so these can be written directly without touching the command line.

Note there is deliberately no tool here for assigning a DMX address. Eos
provides no ``/eos/set/patch/<channel>/address``; addressing has to go through
the command line with the Patch display focused, because in Live ``At`` means
intensity rather than address. Use :func:`command_line` for that.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..app import mcp
from ..errors import EosValidationError
from ._common import TargetNumber, ToolResult, guarded, send

#: Eos provides ten free-text patch fields per channel.
TextFieldIndex = Annotated[int, Field(ge=1, le=10, description="Patch text field, 1-10")]


def _clean(value: str, field: str) -> str:
    """Validate free text bound for a patch field.

    The text is an OSC *argument*, not part of the address, so it needs no
    address-character validation - but a stray newline would be silently
    truncated by the console, and an empty string is almost always a mistake.
    """
    text = value.strip()
    if not text:
        raise EosValidationError(f"{field} must not be empty")
    if "\n" in text or "\r" in text:
        raise EosValidationError(f"{field} must be a single line, got {value!r}")
    return text


@mcp.tool()
@guarded("set_patch_label")
def set_patch_label(channel: TargetNumber, label: str) -> ToolResult:
    """Sets the Label field of a channel in Patch.

    Args:
        channel: The channel number to label.
        label: The label text, e.g. "FOH Bar 1".
    """
    text = _clean(label, "label")
    return send(
        f"/eos/set/patch/{channel}/label",
        text,
        action="set_patch_label",
        detail=f"Labelled channel {channel} {text!r}",
    )


@mcp.tool()
@guarded("set_patch_text")
def set_patch_text(channel: TargetNumber, index: TextFieldIndex, text: str) -> ToolResult:
    """Sets one of the ten free-text fields of a channel in Patch.

    Useful for data the Label field has no room for - position, purpose, or a
    note about a circuit that must not be dimmed.

    Args:
        channel: The channel number.
        index: Which text field to write, 1-10.
        text: The text to store.
    """
    value = _clean(text, "text")
    return send(
        f"/eos/set/patch/{channel}/text{index}",
        value,
        action="set_patch_text",
        detail=f"Set channel {channel} text{index} to {value!r}",
    )


@mcp.tool()
@guarded("set_patch_gel")
def set_patch_gel(channel: TargetNumber, gel: str) -> ToolResult:
    """Sets the Gel field of a channel in Patch.

    Args:
        channel: The channel number.
        gel: A gel string such as "L201", "R375" or "AP1150".
    """
    text = _clean(gel, "gel")
    return send(
        f"/eos/set/patch/{channel}/gel",
        text,
        action="set_patch_gel",
        detail=f"Set channel {channel} gel to {text!r}",
    )

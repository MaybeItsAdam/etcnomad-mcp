"""Validation for values interpolated into OSC addresses.

Tool arguments are built into addresses with f-strings. Without validation a
``/`` in an argument silently redirects the message to a different OSC address
on a live console - so every dynamic segment is checked here first.

OSC 1.0 additionally reserves ``# * , ? [ ] { }`` in address patterns; the
character classes below exclude all of them.
"""

from __future__ import annotations

import re

from ..errors import EosValidationError

#: A single address segment: hardkey names, parameter names, modifiers.
#: Covers Eos values such as ``go_0``, ``stop``, ``Data``, ``pan``, ``+%``.
SEGMENT_RE = re.compile(r"^[A-Za-z0-9_+%-]+$")

#: Cue numbers, including point cues such as ``1.5`` and ``12.25``.
CUE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?$")

#: A channel or channel range as typed on the command line, e.g. ``1``,
#: ``1 Thru 10``, ``1+5+9``.
CHANNEL_SPEC_RE = re.compile(r"^[A-Za-z0-9_+\- ]+$")

#: A fully-built OSC address: absolute, no wildcard or reserved characters.
ADDRESS_RE = re.compile(r"^/[A-Za-z0-9_+%/.-]*$")


def segment(value: str, field: str) -> str:
    """Validate a single OSC address segment.

    Args:
        value: The candidate segment.
        field: Name of the tool argument, used in the error message.

    Returns:
        The validated segment unchanged.

    Raises:
        EosValidationError: If the value is empty or contains a character that
            is not safe in an OSC address (notably ``/``).
    """
    text = value.strip()
    if not text:
        raise EosValidationError(f"{field} must not be empty")
    if not SEGMENT_RE.match(text):
        raise EosValidationError(
            f"{field} may only contain letters, digits, '_', '+', '%' and '-', got {value!r}"
        )
    return text


def cue_number(value: str | int | float, field: str = "cue_number") -> str:
    """Validate a cue number, allowing point cues such as ``1.5``."""
    text = str(value).strip()
    if not CUE_NUMBER_RE.match(text):
        raise EosValidationError(f"{field} must be a number such as '5' or '1.5', got {value!r}")
    return text


def channel_spec(value: str, field: str = "channel") -> str:
    """Validate a channel number or range expression."""
    text = " ".join(value.split())
    if not text:
        raise EosValidationError(f"{field} must not be empty")
    if not CHANNEL_SPEC_RE.match(text):
        raise EosValidationError(
            f"{field} must be a channel or range such as '5' or '1 Thru 10', got {value!r}"
        )
    return text


def validate_address(address: str) -> str:
    """Validate a fully-assembled OSC address before it is sent."""
    if not ADDRESS_RE.match(address):
        raise EosValidationError(f"Refusing to send malformed OSC address {address!r}")
    return address

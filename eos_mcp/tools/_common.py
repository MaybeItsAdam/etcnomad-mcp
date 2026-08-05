"""Shared helpers for the tool modules.

Every tool returns a structured result rather than prose. A model calling these
tools needs to be able to tell success from failure programmatically; a bare
error string is indistinguishable from a success string.

Result shape::

    {"ok": True,  "action": "set_level", "detail": "...", "address": "/eos/at"}
    {"ok": False, "action": "set_level", "error": "..."}
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Annotated, Any, Literal, TypeVar

from pydantic import Field

from ..errors import EosError
from ..logging_setup import get_logger
from ..osc.client import ArgValue, client

logger = get_logger(__name__)

#: What every tool returns.
ToolResult = dict[str, Any]

F = TypeVar("F", bound=Callable[..., ToolResult])

# --- Shared parameter types ----------------------------------------------
# These become JSON Schema `enum` / `minimum` / `maximum` entries, so FastMCP
# rejects out-of-range arguments before the tool body runs and the model sees
# the valid set in the tool definition.

#: Level modifiers accepted by /eos/at, /eos/chan/<n> and /eos/group/<n>.
LevelModifier = Literal["out", "home", "remdim", "level", "full", "min", "max", "+%", "-%"]

#: Modifiers accepted by /eos/param/<name>. Eos has no `remdim` for parameters.
ParamModifier = Literal["out", "home", "level", "full", "min", "max", "+%", "-%"]

#: Buttons attached to a fader.
FaderAction = Literal["load", "unload", "stop", "fire"]

#: Intensity / focus / colour / beam palettes.
PaletteType = Literal["intensity", "focus", "color", "beam"]

#: An intensity percentage.
Percent = Annotated[float, Field(ge=0, le=100, description="Percentage, 0-100")]

#: A normalised 0.0-1.0 control value.
Normalised = Annotated[float, Field(ge=0, le=1, description="Normalised value, 0.0-1.0")]

#: A 1-based console target number (cue list, group, preset, ...).
TargetNumber = Annotated[int, Field(ge=1, description="1-based target number")]

#: An 8-bit DMX output level.
DmxValue = Annotated[int, Field(ge=0, le=255, description="8-bit DMX level, 0-255")]

#: A fader or direct-select bank index. Eos numbers some banks from 0.
BankIndex = Annotated[int, Field(ge=0, description="Bank index as configured on the console")]


def success(action: str, detail: str, **extra: Any) -> ToolResult:
    """Build a successful tool result."""
    return {"ok": True, "action": action, "detail": detail, **extra}


def failure(action: str, error: str, **extra: Any) -> ToolResult:
    """Build a failed tool result."""
    return {"ok": False, "action": action, "error": error, **extra}


def guarded(action: str) -> Callable[[F], F]:
    """Convert any :class:`EosError` raised by a tool into a failure result.

    Keeps validation and transport errors from propagating into the MCP layer,
    where they would surface as an opaque protocol error rather than something
    the caller can read and act on.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
            try:
                return fn(*args, **kwargs)
            except EosError as exc:
                logger.warning("%s failed: %s", action, exc)
                return failure(action, str(exc))

        return wrapper  # type: ignore[return-value]

    return decorator


def send(
    address: str,
    args: ArgValue | list[ArgValue] | None = None,
    *,
    action: str,
    detail: str,
    **extra: Any,
) -> ToolResult:
    """Send one OSC message and report the outcome.

    Raises:
        EosError: On validation or transport failure - callers are wrapped in
            :func:`guarded`, which turns it into a failure result.
    """
    client.send(address, args)
    return success(action, detail, address=address, **extra)


def press(address: str, *, action: str, detail: str, **extra: Any) -> ToolResult:
    """Send a button down/up pair, the way Eos expects hardkey presses."""
    client.send(address, 1.0)
    client.send(address, 0.0)
    return success(action, detail, address=address, **extra)

"""Shared console state, populated by the OSC listener thread.

The listener writes from its own thread while tools read from the MCP request
thread, so every access goes through ``state_lock``. Tools should call
:func:`snapshot` and then format outside the lock rather than holding it while
building strings.
"""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field, fields

# --- Typed state model ---------------------------------------------------


@dataclass
class Fader:
    level: float = 0.0
    label: str = ""


@dataclass
class FaderBank:
    bank_label: str = ""
    faders: dict[int, Fader] = field(default_factory=dict)


@dataclass
class DirectSelectBank:
    label: str = ""
    buttons: dict[int, str] = field(default_factory=dict)


@dataclass
class EosState:
    """Everything the console has told us so far.

    ``None`` consistently means "the console has not reported this yet", which
    is distinct from any real value. ``live_blind_state`` in particular must not
    default to Live - claiming a console is live when we do not know is the
    dangerous direction to be wrong in.
    """

    active_cue_list: str | None = None
    active_cue_number: str | None = None
    active_cue_percent: float = 0.0
    active_cue_text: str = ""
    pending_cue_list: str | None = None
    pending_cue_number: str | None = None
    pending_cue_text: str = ""
    live_blind_state: int | None = None
    command_line: str = ""
    active_channels: str = ""
    faders: dict[int, FaderBank] = field(default_factory=dict)
    direct_selects: dict[int, DirectSelectBank] = field(default_factory=dict)
    wheel_mode: object | None = None
    pantilt: list[float] = field(default_factory=list)
    xyz: list[float] = field(default_factory=list)
    #: ``time.monotonic()`` of the most recent OSC message that changed state.
    last_update: float | None = None

    @property
    def live_blind_label(self) -> str:
        """``"Live"``, ``"Blind"``, or ``"unknown"`` if nothing was reported."""
        if self.live_blind_state is None:
            return "unknown"
        return "Live" if self.live_blind_state == 1 else "Blind"

    @property
    def has_data(self) -> bool:
        """Whether the console has sent us anything at all."""
        return self.last_update is not None


state = EosState()
state_lock = threading.Lock()


def snapshot() -> EosState:
    """Return an independent copy of the current state, taken under the lock."""
    with state_lock:
        return copy.deepcopy(state)


def reset_state() -> None:
    """Restore pristine state in place. Used by tests to isolate cases.

    Mutates the existing object rather than rebinding the module global, because
    other modules hold a direct reference via ``from .state import state``.
    """
    pristine = EosState()
    with state_lock:
        for f in fields(EosState):
            setattr(state, f.name, copy.deepcopy(getattr(pristine, f.name)))

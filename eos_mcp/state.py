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
class Wheel:
    """One encoder wheel: a live parameter of the current selection.

    Eos publishes these whenever the selection changes, which makes them the
    only way to read what a channel is actually *doing* - its pan, tilt and
    colour - rather than what has been assigned to it.
    """

    name: str = ""
    group: int = 0
    level: float = 0.0


@dataclass
class ShowTarget:
    """One numbered record in the show - a sub, effect, group, cue, and so on.

    ``number`` stays a string because Eos target numbers are not integers: cues
    can be ``1.5``, and patch entries carry a part as ``30/2``.
    """

    target_type: str
    number: str
    label: str = ""
    uid: str = ""
    #: Type-specific fields decoded from the reply, e.g. a patch entry's
    #: manufacturer, model and address. Empty for types with nothing beyond
    #: a label.
    extra: dict[str, object] = field(default_factory=dict)


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
    #: Increments on every command line echo, including ones whose text is
    #: identical to the last. Text comparison cannot tell "the console did not
    #: reply" from "the console replied with the same thing".
    command_line_seq: int = 0
    active_channels: str = ""
    faders: dict[int, FaderBank] = field(default_factory=dict)
    direct_selects: dict[int, DirectSelectBank] = field(default_factory=dict)
    wheel_mode: object | None = None
    #: Encoder wheels for the current selection, keyed by wheel index.
    wheels: dict[int, Wheel] = field(default_factory=dict)
    #: Bumped whenever a wheel is reported, so a caller can tell a fresh set
    #: from the previous selection's leftovers.
    wheels_seq: int = 0
    pantilt: list[float] = field(default_factory=list)
    xyz: list[float] = field(default_factory=list)
    #: Which show is loaded. Without this there is no way to tell whether the
    #: console holds the show you think it does - and auditing or writing to
    #: the wrong show is worse than doing nothing.
    show_name: str | None = None
    show_path: str | None = None
    #: ``True`` once Eos reports a save. Show-file settings, including OSC
    #: transmit, are lost on restart if the show was never saved.
    show_saved: bool | None = None
    eos_version: str | None = None
    #: How many records Eos says exist, keyed by target type ("sub", "fx", ...).
    target_counts: dict[str, int] = field(default_factory=dict)
    #: Collected records, keyed by target type then target number.
    show_targets: dict[str, dict[str, ShowTarget]] = field(default_factory=dict)
    #: ``time.monotonic()`` of the most recent OSC message that changed state.
    last_update: float | None = None
    #: ``host:port`` of whoever sent the most recent datagram. Any process on
    #: the machine can send to the listener, so liveness alone does not mean
    #: the console is talking to us.
    last_sender: str | None = None

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

"""Listener tests, driven through the real python-osc dispatcher.

Messages are built and dispatched exactly as they would be off the wire, so
these cover address routing as well as handler logic.
"""

from __future__ import annotations

from typing import Any

import pytest
from pythonosc import osc_message_builder

from eos_mcp.osc.listener import build_dispatcher
from eos_mcp.state import snapshot


@pytest.fixture
def dispatch():  # type: ignore[no-untyped-def]
    """Return a function that pushes a message through the real dispatcher."""
    disp = build_dispatcher()

    def _dispatch(address: str, *args: Any) -> None:
        builder = osc_message_builder.OscMessageBuilder(address=address)
        for arg in args:
            builder.add_arg(arg)
        disp.call_handlers_for_packet(builder.build().dgram, ("127.0.0.1", 9001))

    return _dispatch


# --- Cue numbers ---------------------------------------------------------


def test_active_cue_whole_number(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/active/cue/1/5", 0.5)
    s = snapshot()
    assert (s.active_cue_list, s.active_cue_number) == ("1", "5")
    assert s.active_cue_percent == pytest.approx(0.5)


def test_active_cue_accepts_point_cues(dispatch) -> None:  # type: ignore[no-untyped-def]
    """Regression: point cues were dropped, leaving stale state reported as current."""
    dispatch("/eos/out/active/cue/1/1.5", 0.25)
    s = snapshot()
    assert (s.active_cue_list, s.active_cue_number) == ("1", "1.5")
    assert s.active_cue_percent == pytest.approx(0.25)


def test_pending_cue_accepts_point_cues(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/pending/cue/2/10.75")
    s = snapshot()
    assert (s.pending_cue_list, s.pending_cue_number) == ("2", "10.75")


def test_cue_text_is_not_parsed_as_a_cue_number(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/active/cue/text", "Act 1 Top")
    s = snapshot()
    assert s.active_cue_text == "Act 1 Top"
    assert s.active_cue_number is None


def test_active_cue_without_percent_argument(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/active/cue/1/5")
    assert snapshot().active_cue_number == "5"


# --- Fader routing -------------------------------------------------------
# python-osc expands a registered `*` with `.*?`, which crosses `/`, so all
# three fader handlers see every fader message. The anchored regex in each
# handler is what keeps them from corrupting each other's data.


def test_fader_level_label_and_bank_label_stay_separate(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/fader/1", "Bank One")
    dispatch("/eos/out/fader/1/2", 0.75)
    dispatch("/eos/out/fader/1/2/name", "House Lights")

    bank = snapshot().faders[1]
    assert bank.bank_label == "Bank One"
    assert bank.faders[2].level == pytest.approx(0.75)
    assert bank.faders[2].label == "House Lights"


def test_fader_level_accepts_integer_zero(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/fader/1/2", 0)
    assert snapshot().faders[1].faders[2].level == pytest.approx(0.0)


def test_fader_level_ignores_string_payload(dispatch) -> None:  # type: ignore[no-untyped-def]
    """A name arriving on the level address must not be coerced into a level."""
    dispatch("/eos/out/fader/3/4", "Not A Level")
    faders = snapshot().faders
    assert 3 not in faders or 4 not in faders[3].faders


# --- Direct selects ------------------------------------------------------


def test_direct_select_bank_and_buttons(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/ds/1", "Colour Palettes")
    dispatch("/eos/out/ds/1/3", "Deep Blue")
    ds = snapshot().direct_selects[1]
    assert ds.label == "Colour Palettes"
    assert ds.buttons[3] == "Deep Blue"


# --- Scalars -------------------------------------------------------------


@pytest.mark.parametrize(("value", "expected"), [(1, "Live"), (0, "Blind")])
def test_live_blind_state(dispatch, value: int, expected: str) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/event/state", value)
    assert snapshot().live_blind_label == expected


def test_live_blind_unknown_before_any_message() -> None:
    assert snapshot().live_blind_label == "unknown"


def test_command_line_from_user_address(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/user/1/cmd", "Chan 1 At 50")
    assert snapshot().command_line == "Chan 1 At 50"


def test_active_channels(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/active/chan", "1 Thru 10")
    assert snapshot().active_channels == "1 Thru 10"


def test_pantilt_and_xyz(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/pantilt", 10.0, -20.0)
    dispatch("/eos/out/xyz", 1.0, 2.0, 3.0)
    s = snapshot()
    assert s.pantilt == [pytest.approx(10.0), pytest.approx(-20.0)]
    assert s.xyz == [pytest.approx(1.0), pytest.approx(2.0), pytest.approx(3.0)]


# --- Liveness and resilience ---------------------------------------------


def test_last_update_is_set_by_any_message(dispatch) -> None:  # type: ignore[no-untyped-def]
    assert snapshot().last_update is None
    dispatch("/eos/out/cmd", "Live")
    assert snapshot().last_update is not None


def test_unmodelled_message_still_counts_as_liveness(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/something/we/do/not/model", 1)
    assert snapshot().has_data


def test_handler_exception_does_not_propagate(dispatch) -> None:  # type: ignore[no-untyped-def]
    """A malformed payload must not kill the listener thread."""
    dispatch("/eos/out/active/cue/1/5", "not-a-number")
    assert snapshot().active_cue_number == "5"

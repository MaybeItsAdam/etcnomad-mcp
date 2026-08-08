"""Tests for show-data enumeration.

The get replies are the only way to learn what a show already contains, so the
routing is covered against genuine datagrams rather than by calling handlers
directly - an address that fails to match silently yields an empty ledger,
which reads as "nothing exists" rather than as an error.
"""

from __future__ import annotations

from typing import Any

import pytest
from pythonosc import osc_message_builder

from eos_mcp.osc.listener import build_dispatcher
from eos_mcp.state import snapshot
from eos_mcp.tools.inventory import _sort_key


@pytest.fixture
def dispatch():  # type: ignore[no-untyped-def]
    disp = build_dispatcher()

    def _dispatch(address: str, *args: Any) -> None:
        builder = osc_message_builder.OscMessageBuilder(address=address)
        for arg in args:
            builder.add_arg(arg)
        disp.call_handlers_for_packet(builder.build().dgram, ("127.0.0.1", 8001))

    return _dispatch


# --- Counts --------------------------------------------------------------


def test_count_is_recorded(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/get/sub/count", 12)
    assert snapshot().target_counts["sub"] == 12


def test_cue_count_is_scoped_to_its_list(dispatch) -> None:  # type: ignore[no-untyped-def]
    """Cue counts nest under a list number and must not collide."""
    dispatch("/eos/out/get/cue/1/count", 40)
    dispatch("/eos/out/get/cue/2/count", 7)
    counts = snapshot().target_counts
    assert counts["cue/1"] == 40
    assert counts["cue/2"] == 7


# --- Detail records ------------------------------------------------------


def test_detail_captures_number_and_label(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/get/sub/5/list/0/3", 0, "uid-5", "house lights")
    rec = snapshot().show_targets["sub"]["5"]
    assert (rec.number, rec.label, rec.uid) == ("5", "house lights", "uid-5")


def test_later_packets_do_not_erase_the_label(dispatch) -> None:  # type: ignore[no-untyped-def]
    """Eos splits a record across packets; only the first carries the label."""
    dispatch("/eos/out/get/fx/800/list/0/4", 0, "uid-800", "ballyhoo")
    dispatch("/eos/out/get/fx/800/list/1/4", 1, "", "")
    assert snapshot().show_targets["fx"]["800"].label == "ballyhoo"


def test_nested_target_numbers_survive(dispatch) -> None:  # type: ignore[no-untyped-def]
    """Cues carry list/number/part, and patch entries carry channel/part."""
    dispatch("/eos/out/get/cue/1/2.5/0/list/0/5", 0, "uid-c", "blackout")
    dispatch("/eos/out/get/patch/30/1/list/0/5", 0, "uid-p", "mover SL")
    targets = snapshot().show_targets
    assert targets["cue"]["1/2.5/0"].label == "blackout"
    assert targets["patch"]["30/1"].label == "mover SL"


def test_version_reply_is_not_mistaken_for_a_record(dispatch) -> None:  # type: ignore[no-untyped-def]
    """/eos/out/get/version has no count or list segments to match."""
    dispatch("/eos/out/get/version", "3.3.8.7")
    s = snapshot()
    assert "version" not in s.show_targets
    assert "version" not in s.target_counts


# --- Ordering ------------------------------------------------------------


def test_targets_sort_numerically_not_lexically() -> None:
    numbers = ["10", "2", "1.5"]
    assert sorted(numbers, key=_sort_key) == ["1.5", "2", "10"]


def test_non_numeric_targets_sort_last_without_raising() -> None:
    assert _sort_key("abc")[0] == float("inf")

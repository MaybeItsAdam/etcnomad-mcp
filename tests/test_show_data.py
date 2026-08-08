"""Show identity, patch detail, and cache invalidation.

These cover the reads that were missing or lossy, each of which caused a wrong
conclusion during a real session: patch entries that looked unlabelled when the
fixture type was sitting in the same packet, and no way to tell which show was
loaded while two candidate archives sat on disk.
"""

from __future__ import annotations

from typing import Any

import pytest
from pythonosc import osc_message_builder

from eos_mcp.osc.listener import build_dispatcher
from eos_mcp.state import snapshot


@pytest.fixture
def dispatch():  # type: ignore[no-untyped-def]
    disp = build_dispatcher()

    def _dispatch(address: str, *args: Any) -> None:
        builder = osc_message_builder.OscMessageBuilder(address=address)
        for arg in args:
            builder.add_arg(arg)
        disp.call_handlers_for_packet(builder.build().dgram, ("127.0.0.1", 8001))

    return _dispatch


# --- Patch detail --------------------------------------------------------


def test_patch_reports_manufacturer_and_model(dispatch) -> None:  # type: ignore[no-untyped-def]
    """Without these a dimmer is indistinguishable from a moving light."""
    dispatch(
        "/eos/out/get/patch/30/1/list/0/2",
        0,
        "uid-30",
        "",
        "Gear4Music",
        "Orbit_70_9ch",
        30,
        30,
        100,
    )
    rec = snapshot().show_targets["patch"]["30/1"]
    assert rec.extra["manufacturer"] == "Gear4Music"
    assert rec.extra["model"] == "Orbit_70_9ch"
    assert rec.extra["address"] == 30


def test_empty_patch_fields_are_omitted(dispatch) -> None:  # type: ignore[no-untyped-def]
    """An absent manufacturer should not appear as an empty string."""
    dispatch("/eos/out/get/patch/1/1/list/0/2", 0, "uid-1", "", "", "", 1)
    assert "manufacturer" not in snapshot().show_targets["patch"]["1/1"].extra


def test_types_without_extra_fields_stay_clean(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/get/group/5/list/0/1", 0, "uid-g", "warms")
    assert snapshot().show_targets["group"]["5"].extra == {}


# --- Show identity -------------------------------------------------------


def test_show_name_is_captured(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/show/name", "Camden2026 rattlepole")
    assert snapshot().show_name == "Camden2026 rattlepole"


def test_show_path_is_captured(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/get/show/path", "/Users/adam/Documents/ETC/Eos/Shows/camden.esf3d")
    assert snapshot().show_path.endswith("camden.esf3d")


def test_save_event_is_recorded(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/event/show/saved")
    assert snapshot().show_saved is True


# --- Cache invalidation --------------------------------------------------


def test_notify_drops_cached_targets_of_that_type(dispatch) -> None:  # type: ignore[no-untyped-def]
    """Stale enumeration would report an occupied sub as free."""
    dispatch("/eos/out/get/sub/5/list/0/1", 0, "uid-5", "Ch30 Ballyhoo")
    dispatch("/eos/out/get/sub/count", 1)
    assert snapshot().show_targets["sub"]

    dispatch("/eos/out/notify/sub/list/0/1", 7)
    s = snapshot()
    assert "sub" not in s.show_targets
    assert "sub" not in s.target_counts


def test_notify_leaves_other_types_alone(dispatch) -> None:  # type: ignore[no-untyped-def]
    dispatch("/eos/out/get/fx/800/list/0/1", 0, "uid-800", "Ballyhoo")
    dispatch("/eos/out/notify/sub/list/0/1", 7)
    assert snapshot().show_targets["fx"]["800"].label == "Ballyhoo"


def test_cue_notify_clears_every_list_of_that_type(dispatch) -> None:  # type: ignore[no-untyped-def]
    """Cue notifications carry a list number; the whole type is re-read anyway."""
    dispatch("/eos/out/get/cue/1/count", 40)
    dispatch("/eos/out/get/cue/2/count", 7)
    dispatch("/eos/out/notify/cue/1/list/0/1", 3)
    assert snapshot().target_counts == {}

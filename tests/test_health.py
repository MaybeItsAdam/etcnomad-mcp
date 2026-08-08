"""Tests that connection health cannot be faked by local traffic.

The server used to report "Healthy - last OSC message from the console" for a
datagram sent by an unrelated local process. A diagnostic that can be fooled is
worse than none: it turns "the link is down" into "the console has no data",
and the next tool call trusts empty state.
"""

from __future__ import annotations

import dataclasses

import pytest

from eos_mcp.state import state, state_lock
from eos_mcp.tools import queries
from eos_mcp.tools.queries import get_connection_health


def _received_from(sender: str) -> None:
    """Simulate a datagram arriving from ``host:port``."""
    with state_lock:
        state.last_sender = sender
        state.last_update = 1000.0


@pytest.fixture
def _running_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    """A listener that is bound and healthy, so sender logic is what is tested."""
    monkeypatch.setattr(queries.listener, "bind_error", None, raising=False)
    monkeypatch.setattr(type(queries.listener), "is_running", property(lambda self: True))
    monkeypatch.setattr(
        type(queries.listener), "bound_address", property(lambda self: "0.0.0.0:8001")
    )


def test_console_traffic_reads_as_healthy(_running_listener: None) -> None:
    _received_from(f"{queries.config.eos_ip}:51000")
    result = get_connection_health()
    assert "Healthy" in result["detail"]
    assert result["last_sender"] == f"{queries.config.eos_ip}:51000"


def test_foreign_traffic_does_not_read_as_healthy(_running_listener: None) -> None:
    """The exact failure: a local test packet reported the console as healthy."""
    _received_from("192.0.2.77:9999")
    result = get_connection_health()
    assert "Healthy" not in result["detail"]
    assert "192.0.2.77" in result["detail"]
    assert "not proof" in result["detail"]


def test_sender_is_always_reported(_running_listener: None) -> None:
    _received_from("192.0.2.77:9999")
    assert get_connection_health()["last_sender"] == "192.0.2.77:9999"


def test_loopback_console_explains_a_differing_sender(
    _running_listener: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eos on this machine replies from its LAN interface - that is expected."""
    monkeypatch.setattr(queries, "config", dataclasses.replace(queries.config, eos_ip="127.0.0.1"))
    _received_from("10.97.28.103:51000")
    detail = get_connection_health()["detail"]
    assert "expected" in detail


def test_routed_console_does_not_get_the_loopback_excuse(
    _running_listener: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(queries, "config", dataclasses.replace(queries.config, eos_ip="10.0.0.5"))
    _received_from("192.0.2.77:9999")
    assert "expected" not in get_connection_health()["detail"]


# --- Sender matching -----------------------------------------------------


@pytest.mark.parametrize(
    ("sender", "console_ip", "expected"),
    [
        ("10.0.0.5:8001", "10.0.0.5", True),
        ("10.0.0.55:8001", "10.0.0.5", False),
        ("127.0.0.1:8001", "127.0.0.1", True),
        (None, "10.0.0.5", False),
        ("", "10.0.0.5", False),
    ],
)
def test_sender_matching(
    sender: str | None, console_ip: str, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(queries, "config", dataclasses.replace(queries.config, eos_ip=console_ip))
    assert queries._sender_is_console(sender) is expected


# --- Show name ------------------------------------------------------------


def test_show_name_falls_back_to_the_filename() -> None:
    """Eos reported a path but no name on a real console."""
    assert (
        queries._name_from_path("/Users/a/ETC/Eos/ShowArchive/Camden2026 rattlepole.esf3d")
        == "Camden2026 rattlepole"
    )


def test_windows_style_paths_are_handled() -> None:
    assert queries._name_from_path(r"C:\Users\a\Shows\panto.esf3d") == "panto"


def test_no_path_yields_no_name() -> None:
    assert queries._name_from_path(None) is None
    assert queries._name_from_path("") is None

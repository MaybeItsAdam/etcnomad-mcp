"""End-to-end over a real UDP socket, with no console involved.

Starts the listener on an ephemeral port, sends genuine OSC datagrams to it, and
checks the state the tools would read.
"""

from __future__ import annotations

import socket
import time

import pytest
from pythonosc import udp_client

from eos_mcp.config import EosConfig
from eos_mcp.osc.listener import OscListener
from eos_mcp.state import snapshot


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(predicate, timeout: float = 2.0) -> bool:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def running_listener():  # type: ignore[no-untyped-def]
    port = _free_port()
    listener = OscListener(EosConfig(rx_host="127.0.0.1", port_rx=port))
    assert listener.start(), listener.bind_error
    sender = udp_client.SimpleUDPClient("127.0.0.1", port)
    try:
        yield listener, sender
    finally:
        sender.close()
        listener.stop()


def test_real_datagram_updates_state(running_listener) -> None:  # type: ignore[no-untyped-def]
    listener, client = running_listener

    client.send_message("/eos/out/active/cue/1/1.5", 0.5)
    client.send_message("/eos/out/active/cue/text", "Act 2 Opening")

    assert _wait_for(lambda: snapshot().active_cue_text == "Act 2 Opening")
    s = snapshot()
    assert s.active_cue_number == "1.5"
    assert s.last_update is not None
    assert listener.is_running


def test_listener_reports_bind_failure_instead_of_dying() -> None:
    """Two listeners on one port: the second must explain itself, not vanish."""
    port = _free_port()
    cfg = EosConfig(rx_host="127.0.0.1", port_rx=port)

    first = OscListener(cfg)
    assert first.start()
    second = OscListener(cfg)
    try:
        assert second.start() is False
        assert second.bind_error is not None
        assert str(port) in second.bind_error
        assert second.is_running is False
    finally:
        first.stop()
        second.stop()


def test_stop_releases_the_port() -> None:
    port = _free_port()
    cfg = EosConfig(rx_host="127.0.0.1", port_rx=port)

    first = OscListener(cfg)
    assert first.start()
    first.stop()
    assert first.is_running is False

    second = OscListener(cfg)
    try:
        assert second.start(), second.bind_error
    finally:
        second.stop()

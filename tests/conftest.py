"""Shared fixtures. Nothing here needs a real console."""

from __future__ import annotations

from typing import Any

import pytest

from eos_mcp.osc.client import client
from eos_mcp.state import reset_state


class RecordingUDPClient:
    """Stands in for ``pythonosc.udp_client.SimpleUDPClient``."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.messages: list[tuple[str, Any]] = []
        self.fail_with = fail_with

    def send_message(self, address: str, value: Any) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.messages.append((address, value))


@pytest.fixture(autouse=True)
def clean_state() -> None:
    """Every test starts with an empty console state."""
    reset_state()


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> RecordingUDPClient:
    """Capture OSC messages instead of putting them on the wire."""
    recorder = RecordingUDPClient()
    monkeypatch.setattr(client, "_client", recorder)
    return recorder


@pytest.fixture
def failing_send(monkeypatch: pytest.MonkeyPatch) -> RecordingUDPClient:
    """Make every send fail the way an unreachable console would."""
    recorder = RecordingUDPClient(fail_with=OSError("Network is unreachable"))
    monkeypatch.setattr(client, "_client", recorder)
    return recorder

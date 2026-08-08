"""Tests that command_line reports what the console actually did.

Every case here is a real failure observed while driving a console: the send
succeeded, the tool reported ok, and the show was unchanged. The happy path was
already covered; these cover the lying path.
"""

from __future__ import annotations

from typing import Any

import pytest

from eos_mcp.state import state, state_lock
from eos_mcp.tools import levels
from eos_mcp.tools.levels import command_line

from .conftest import RecordingUDPClient


class FakeConsole:
    """A console that echoes its command line back when something is sent.

    Confirmation hinges on the reply arriving *after* the send, so a test that
    pre-sets the state would pass while proving nothing.
    """

    def __init__(self) -> None:
        self.reply: str | None = None

    def will_reply(self, text: str) -> None:
        self.reply = text


@pytest.fixture
def console(sent: RecordingUDPClient, monkeypatch: pytest.MonkeyPatch) -> FakeConsole:
    fake = FakeConsole()
    original = sent.send_message

    def send_message(address: str, value: Any) -> None:
        original(address, value)
        if fake.reply is not None:
            with state_lock:
                state.command_line = fake.reply

    monkeypatch.setattr(sent, "send_message", send_message)
    return fake


def test_syntax_error_is_a_failure(console: FakeConsole) -> None:
    """`Fader 6 Sub 5` returned ok: true while the console showed an error."""
    console.will_reply("LIVE: Cue  0.1 : Fader 1 / 6 Sub - Error: Syntax Error")
    result = command_line("Fader 6 Sub 5 Enter")
    assert result["ok"] is False
    assert "Syntax Error" in result["error"]
    assert "Fader 6 Sub 5 Enter" in result["error"]


def test_setup_context_is_not_confirmed(console: FakeConsole) -> None:
    """Setup swallows keystrokes; an effect copy silently did nothing."""
    console.will_reply("BLIND: Setup : ")
    result = command_line("Effect 909 Copy_To Effect 800 Enter")
    assert result["confirmed"] is False
    assert result["console_context"] == "Setup"
    assert "Setup" in result["detail"]


def test_live_context_is_confirmed(console: FakeConsole) -> None:
    console.will_reply("LIVE: Cue  0.1 : Chan 30 Effect 800 #")
    result = command_line("Chan 30 Effect 800 Enter")
    assert result["ok"] is True
    assert result["confirmed"] is True
    assert result["console_context"] == "Cue  0.1"


def test_silent_console_is_not_confirmed(console: FakeConsole) -> None:
    """With no return path there is no evidence either way - say so."""
    result = command_line("Chan 30 At Full Enter")
    assert result["ok"] is True
    assert result["confirmed"] is False
    assert "NOT CONFIRMED" in result["detail"]


def test_the_command_still_leaves_the_machine(
    console: FakeConsole, sent: RecordingUDPClient
) -> None:
    """Confirmation must not change what is actually sent."""
    console.will_reply("LIVE: Cue  0.1 : Record Sub 5 #")
    command_line("Record Sub 5 Enter")
    assert sent.messages == [("/eos/newcmd", "Record Sub 5 Enter")]


def test_readback_is_always_reported(console: FakeConsole) -> None:
    console.will_reply("LIVE: Cue  0.1 : Record Sub 5 #")
    result = command_line("Record Sub 5 Enter")
    assert result["console_command_line"] == "LIVE: Cue  0.1 : Record Sub 5 #"


# --- Context parsing -----------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("LIVE: Cue  0.1 : Chan 30 @ Full #", "Cue  0.1"),
        ("BLIND: Setup : ", "Setup"),
        ("LIVE: Cue  0.1 : ", "Cue  0.1"),
        ("", ""),
        ("nonsense", ""),
    ],
)
def test_context_extraction(line: str, expected: str) -> None:
    assert levels._context_of(line) == expected

"""Tool behaviour.

``@mcp.tool()`` returns the plain function, so tools are called directly here;
FastMCP's own schema validation is covered separately in test_schemas.py.
"""

from __future__ import annotations

import pytest

from eos_mcp.tools.color_position import set_color_rgb
from eos_mcp.tools.cue_list_banks import select_cue_list_bank_cue
from eos_mcp.tools.faders import control_fader_button, press_direct_select, set_fader
from eos_mcp.tools.keys_macros import press_key, press_softkey
from eos_mcp.tools.levels import apply_modifier, command_line, set_dmx, set_level, set_parameter
from eos_mcp.tools.patch import set_patch_gel, set_patch_label, set_patch_text
from eos_mcp.tools.playback import fire_cue, go_cue
from eos_mcp.tools.presets import fire_palette
from eos_mcp.tools.queries import get_active_cue, get_connection_health, get_live_blind_state
from eos_mcp.tools.selection import select_channel

from .conftest import RecordingUDPClient

# --- Address construction ------------------------------------------------


def test_set_level_sends_to_eos_at(sent: RecordingUDPClient) -> None:
    result = set_level(50.0)
    assert result["ok"] is True
    assert sent.messages == [("/eos/at", 50.0)]


def test_command_line_sends_text_as_argument(sent: RecordingUDPClient) -> None:
    """The command is an OSC argument, never part of the address."""
    result = command_line("Chan 1 Thru 10 At 50")
    assert result["ok"] is True
    assert sent.messages == [("/eos/newcmd", "Chan 1 Thru 10 At 50")]


def test_command_line_resets_the_command_line_by_default(sent: RecordingUDPClient) -> None:
    """Eos appends to whatever is already pending, so reset is the safe default.

    A leftover fragment silently turns the next command into a syntax error, or
    into a different valid command.
    """
    command_line("Chan 1 At 50 Enter")
    assert sent.messages[0][0] == "/eos/newcmd"


def test_command_line_can_append_when_reset_is_false(sent: RecordingUDPClient) -> None:
    result = command_line("Thru 10 At 50", reset=False)
    assert result["ok"] is True
    assert sent.messages == [("/eos/cmd", "Thru 10 At 50")]


def test_fire_cue_supports_point_cues(sent: RecordingUDPClient) -> None:
    result = fire_cue(1, "1.5")
    assert result["ok"] is True
    assert sent.messages == [("/eos/cue/1/1.5/fire", 1.0)]


def test_go_cue_sends_press_and_release(sent: RecordingUDPClient) -> None:
    go_cue()
    assert sent.messages == [("/eos/key/go_0", 1.0), ("/eos/key/go_0", 0.0)]


def test_press_direct_select_sends_press_and_release(sent: RecordingUDPClient) -> None:
    press_direct_select(1, 3)
    assert sent.messages == [("/eos/ds/1/3", 1.0), ("/eos/ds/1/3", 0.0)]


def test_set_fader(sent: RecordingUDPClient) -> None:
    set_fader(1, 2, 0.75)
    assert sent.messages == [("/eos/fader/1/2", 0.75)]


def test_control_fader_button(sent: RecordingUDPClient) -> None:
    control_fader_button(1, 2, "fire")
    assert sent.messages == [("/eos/fader/1/2/fire", [])]


def test_fire_palette_maps_type_to_stem(sent: RecordingUDPClient) -> None:
    fire_palette("color", 4)
    assert sent.messages == [("/eos/cp/fire", 4)]


def test_set_color_rgb_sends_three_components(sent: RecordingUDPClient) -> None:
    set_color_rgb(1.0, 0.0, 0.5)
    assert sent.messages == [("/eos/color/rgb", [1.0, 0.0, 0.5])]


def test_set_dmx(sent: RecordingUDPClient) -> None:
    set_dmx(12, 255)
    assert sent.messages == [("/eos/addr/12/DMX", 255)]


def test_press_softkey(sent: RecordingUDPClient) -> None:
    press_softkey(3)
    assert sent.messages == [("/eos/softkey/3", 1.0), ("/eos/softkey/3", 0.0)]


# --- apply_modifier consolidation ----------------------------------------


def test_apply_modifier_to_selection(sent: RecordingUDPClient) -> None:
    assert apply_modifier("full")["ok"] is True
    assert sent.messages == [("/eos/at/full", [])]


def test_apply_modifier_to_channel(sent: RecordingUDPClient) -> None:
    apply_modifier("out", target="channel", number=5)
    assert sent.messages == [("/eos/chan/5/out", [])]


def test_apply_modifier_to_group(sent: RecordingUDPClient) -> None:
    apply_modifier("home", target="group", number=2)
    assert sent.messages == [("/eos/group/2/home", [])]


def test_apply_modifier_percent_modifiers_survive(sent: RecordingUDPClient) -> None:
    apply_modifier("+%")
    assert sent.messages == [("/eos/at/+%", [])]


def test_apply_modifier_requires_number_for_channel(sent: RecordingUDPClient) -> None:
    result = apply_modifier("out", target="channel")
    assert result["ok"] is False
    assert "number is required" in result["error"]
    assert sent.messages == []


def test_apply_modifier_rejects_number_for_selection(sent: RecordingUDPClient) -> None:
    result = apply_modifier("out", target="selection", number=5)
    assert result["ok"] is False
    assert sent.messages == []


# --- select_channel handles ranges ---------------------------------------


def test_select_channel_single(sent: RecordingUDPClient) -> None:
    select_channel("5")
    assert sent.messages == [("/eos/chan", 5)]


def test_select_channel_range_routes_via_command_line(sent: RecordingUDPClient) -> None:
    result = select_channel("1 Thru 10")
    assert result["ok"] is True
    assert sent.messages == [("/eos/cmd", "Chan 1 Thru 10")]


def test_select_channel_rejects_injection(sent: RecordingUDPClient) -> None:
    result = select_channel("1/2")
    assert result["ok"] is False
    assert sent.messages == []


# --- Validation failures return results, never raise ---------------------


@pytest.mark.parametrize("key", ["go/0", "", "key name", "../cmd"])
def test_press_key_rejects_unsafe_names(key: str, sent: RecordingUDPClient) -> None:
    result = press_key(key)
    assert result["ok"] is False
    assert result["action"] == "press_key"
    assert sent.messages == []


def test_press_key_accepts_real_key(sent: RecordingUDPClient) -> None:
    press_key("go_0")
    assert sent.messages == [("/eos/key/go_0", 1.0), ("/eos/key/go_0", 0.0)]


def test_set_parameter_rejects_slash(sent: RecordingUDPClient) -> None:
    assert set_parameter("pan/tilt", 50.0)["ok"] is False
    assert sent.messages == []


def test_command_line_rejects_empty(sent: RecordingUDPClient) -> None:
    assert command_line("   ")["ok"] is False
    assert sent.messages == []


def test_cue_list_bank_rejects_bad_cue(sent: RecordingUDPClient) -> None:
    assert select_cue_list_bank_cue(1, "1/2")["ok"] is False
    assert sent.messages == []


# --- Transport failures --------------------------------------------------


def test_unreachable_console_returns_failure_not_exception(
    failing_send: RecordingUDPClient,
) -> None:
    result = set_level(50.0)
    assert result["ok"] is False
    assert "Network is unreachable" in result["error"]


def test_failure_result_carries_the_action(failing_send: RecordingUDPClient) -> None:
    assert set_level(50.0)["action"] == "set_level"


# --- Queries -------------------------------------------------------------


def test_get_active_cue_reports_unknown_before_sync() -> None:
    result = get_active_cue()
    assert result["ok"] is True
    assert result["known"] is False


def test_get_active_cue_after_state_update() -> None:
    from eos_mcp.osc.listener import handle_active_cue, handle_active_cue_text

    handle_active_cue("/eos/out/active/cue/1/1.5", 0.5)
    handle_active_cue_text("/eos/out/active/cue/text", "Sunrise")

    result = get_active_cue()
    assert result["known"] is True
    assert result["cue_number"] == "1.5"
    assert result["percent_complete"] == pytest.approx(50.0)
    assert result["label"] == "Sunrise"


def test_live_blind_does_not_claim_live_before_data() -> None:
    """Reporting Live when we do not know is the dangerous direction to be wrong."""
    result = get_live_blind_state()
    assert result["state"] == "unknown"
    assert result["known"] is False


def test_connection_health_reports_no_data_yet() -> None:
    result = get_connection_health()
    assert result["ok"] is True
    assert result["has_data"] is False
    assert "command_target" in result


# --- Patch ---------------------------------------------------------------


def test_set_patch_label_targets_the_channel(sent: RecordingUDPClient) -> None:
    result = set_patch_label(14, "LED power")
    assert result["ok"] is True
    assert sent.messages == [("/eos/set/patch/14/label", "LED power")]


def test_set_patch_text_targets_the_numbered_field(sent: RecordingUDPClient) -> None:
    result = set_patch_text(56, 1, "Bar C")
    assert result["ok"] is True
    assert sent.messages == [("/eos/set/patch/56/text1", "Bar C")]


def test_set_patch_gel_targets_the_gel_field(sent: RecordingUDPClient) -> None:
    result = set_patch_gel(1, "L201")
    assert result["ok"] is True
    assert sent.messages == [("/eos/set/patch/1/gel", "L201")]


@pytest.mark.parametrize("bad", ["", "   ", "two\nlines"])
def test_patch_label_rejects_empty_and_multiline(sent: RecordingUDPClient, bad: str) -> None:
    """A blank label is a mistake, and a newline would be truncated silently."""
    result = set_patch_label(1, bad)
    assert result["ok"] is False
    assert sent.messages == []


# --- Loading faders ------------------------------------------------------


def test_load_to_fader_sends_target_then_load(sent: RecordingUDPClient) -> None:
    """Assignment is command-line target followed by the Load button.

    "Fader 6 Sub 5" is a syntax error on the console; this two-step is the
    only way, and the order matters.
    """
    from eos_mcp.tools.faders import load_to_fader

    result = load_to_fader(1, 6, "Sub 5")
    assert result["ok"] is True
    assert sent.messages == [("/eos/newcmd", "Sub 5"), ("/eos/fader/1/6/load", [])]


def test_load_to_fader_leaves_the_target_unterminated(sent: RecordingUDPClient) -> None:
    """Appending Enter would execute the target instead of loading it."""
    from eos_mcp.tools.faders import load_to_fader

    load_to_fader(1, 6, "Color_Palette 2")
    assert sent.messages[0] == ("/eos/newcmd", "Color_Palette 2")
    assert "Enter" not in str(sent.messages[0][1])


def test_load_to_fader_rejects_an_empty_target(sent: RecordingUDPClient) -> None:
    from eos_mcp.tools.faders import load_to_fader

    result = load_to_fader(1, 6, "   ")
    assert result["ok"] is False
    assert sent.messages == []

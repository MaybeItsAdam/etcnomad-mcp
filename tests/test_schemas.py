"""The generated tool schemas are the contract the model works against.

Constraints declared with ``Literal`` and ``Field`` are enforced by FastMCP
before a tool body runs, so these assertions cover input validation that the
tool functions themselves never see.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from eos_mcp import prompts, tools  # noqa: F401  (registers everything)
from eos_mcp.app import mcp


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict[str, Any]]:
    registered = asyncio.run(mcp._list_tools())
    return {t.name: t.parameters for t in registered}


def test_every_tool_is_registered(schemas: dict[str, dict[str, Any]]) -> None:
    for name in ("set_level", "fire_cue", "sync_state", "get_connection_health"):
        assert name in schemas


def test_vision_tools_are_gone(schemas: dict[str, dict[str, Any]]) -> None:
    assert "capture_visualizer" not in schemas
    assert "capture_camera" not in schemas


def test_superseded_tools_are_gone(schemas: dict[str, dict[str, Any]]) -> None:
    """Replaced by apply_modifier and sync_state respectively."""
    for name in ("set_level_mod", "set_channel_mod", "set_group_mod", "request_setup"):
        assert name not in schemas


def test_level_is_bounded_to_a_percentage(schemas: dict[str, dict[str, Any]]) -> None:
    value = schemas["set_level"]["properties"]["value"]
    assert value["minimum"] == 0
    assert value["maximum"] == 100


def test_fader_level_is_normalised(schemas: dict[str, dict[str, Any]]) -> None:
    level = schemas["set_fader"]["properties"]["level"]
    assert (level["minimum"], level["maximum"]) == (0, 1)


def test_dmx_value_is_eight_bit(schemas: dict[str, dict[str, Any]]) -> None:
    value = schemas["set_dmx"]["properties"]["value"]
    assert (value["minimum"], value["maximum"]) == (0, 255)


def test_softkey_range(schemas: dict[str, dict[str, Any]]) -> None:
    index = schemas["press_softkey"]["properties"]["index"]
    assert (index["minimum"], index["maximum"]) == (1, 12)


def test_modifiers_are_an_enum(schemas: dict[str, dict[str, Any]]) -> None:
    modifier = schemas["apply_modifier"]["properties"]["modifier"]
    assert set(modifier["enum"]) == {
        "out",
        "home",
        "remdim",
        "level",
        "full",
        "min",
        "max",
        "+%",
        "-%",
    }


def test_fader_actions_are_an_enum(schemas: dict[str, dict[str, Any]]) -> None:
    action = schemas["control_fader_button"]["properties"]["action"]
    assert set(action["enum"]) == {"load", "unload", "stop", "fire"}


def test_palette_types_are_an_enum(schemas: dict[str, dict[str, Any]]) -> None:
    palette = schemas["fire_palette"]["properties"]["palette_type"]
    assert set(palette["enum"]) == {"intensity", "focus", "color", "beam"}


def test_every_tool_has_a_description(schemas: dict[str, dict[str, Any]]) -> None:
    registered = asyncio.run(mcp._list_tools())
    missing = [t.name for t in registered if not (t.description or "").strip()]
    assert not missing, f"tools without a docstring: {missing}"

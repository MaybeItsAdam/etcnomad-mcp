"""Importing this package registers every tool with the FastMCP app."""

from . import (
    audit,
    color_position,
    cue_list_banks,
    faders,
    inventory,
    keys_macros,
    levels,
    patch,
    playback,
    presets,
    queries,
    selection,
    wheels,
)

__all__ = [
    "audit",
    "color_position",
    "cue_list_banks",
    "faders",
    "inventory",
    "keys_macros",
    "levels",
    "patch",
    "playback",
    "presets",
    "queries",
    "selection",
    "wheels",
]

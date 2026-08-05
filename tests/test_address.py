"""Address validation is what stops a tool argument redirecting an OSC message."""

from __future__ import annotations

import pytest

from eos_mcp.errors import EosValidationError
from eos_mcp.osc import address as addr


@pytest.mark.parametrize(
    "value", ["go_0", "stop", "Data", "pan", "tilt", "full", "+%", "-%", "remdim", "GoToCue"]
)
def test_segment_accepts_real_eos_values(value: str) -> None:
    assert addr.segment(value, "field") == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "go/0",  # the injection case: escapes into another address
        "../cmd",
        "key name",
        "key*",
        "key?",
        "key[1]",
        "key{a,b}",
        "key#1",
    ],
)
def test_segment_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(EosValidationError):
        addr.segment(value, "field")


def test_segment_error_names_the_field() -> None:
    with pytest.raises(EosValidationError, match="key_name"):
        addr.segment("a/b", "key_name")


@pytest.mark.parametrize("value", ["1", "5", "1.5", "12.25", "0", "100.001"])
def test_cue_number_accepts_whole_and_point_cues(value: str) -> None:
    assert addr.cue_number(value) == value


@pytest.mark.parametrize("value", ["", "1.5.2", "abc", "1/2", "-1", "1e3", "1."])
def test_cue_number_rejects_non_numbers(value: str) -> None:
    with pytest.raises(EosValidationError):
        addr.cue_number(value)


def test_cue_number_accepts_numeric_types() -> None:
    assert addr.cue_number(5) == "5"
    assert addr.cue_number(1.5) == "1.5"


@pytest.mark.parametrize("value", ["1", "1 Thru 10", "1+5+9", "1 Thru 10 - 5"])
def test_channel_spec_accepts_ranges(value: str) -> None:
    assert addr.channel_spec(value)


def test_channel_spec_normalises_whitespace() -> None:
    assert addr.channel_spec("  1   Thru   10 ") == "1 Thru 10"


@pytest.mark.parametrize("value", ["", "1/2", "Chan 1; rm -rf", "1*"])
def test_channel_spec_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(EosValidationError):
        addr.channel_spec(value)


@pytest.mark.parametrize("value", ["/eos/cmd", "/eos/cue/1/1.5/fire", "/eos/at/+%"])
def test_validate_address_accepts_real_addresses(value: str) -> None:
    assert addr.validate_address(value) == value


@pytest.mark.parametrize("value", ["eos/cmd", "", "/eos/cmd *", "/eos/{a,b}", "/eos/#bundle"])
def test_validate_address_rejects_malformed(value: str) -> None:
    with pytest.raises(EosValidationError):
        addr.validate_address(value)

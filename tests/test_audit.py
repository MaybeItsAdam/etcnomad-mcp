"""Audit checks, using label sets taken from a real show.

The duplicates and case variants here are genuine: seven effects named "pulse",
six houselight channels spelled three ways. They are the reason this tool
exists, so they are what it is tested against.
"""

from __future__ import annotations

from eos_mcp.tools.audit import _case_variants, _duplicate_labels, _unlabelled

EFFECTS = [
    {"number": "915", "label": "Ramp"},
    {"number": "920", "label": "pulse"},
    {"number": "921", "label": "pulse"},
    {"number": "922", "label": "police"},
    {"number": "925", "label": "Ramp"},
    {"number": "930", "label": "pulse"},
]

HOUSELIGHTS = [
    {"number": "500", "label": "Houselights"},
    {"number": "501", "label": "HOUSELIGHTS"},
    {"number": "502", "label": "HOUSELIGHTS"},
    {"number": "506", "label": ""},
]


def test_duplicate_labels_are_grouped_with_their_numbers() -> None:
    found = {d["label"]: d["numbers"] for d in _duplicate_labels(EFFECTS)}
    assert found["pulse"] == ["920", "921", "930"]
    assert found["Ramp"] == ["915", "925"]
    assert "police" not in found


def test_case_variants_are_reported_together() -> None:
    variants = _case_variants(HOUSELIGHTS)
    assert len(variants) == 1
    assert variants[0]["variants"] == ["HOUSELIGHTS", "Houselights"]


def test_identical_labels_are_not_a_case_variant() -> None:
    """Exact duplicates are a different finding; do not report them twice."""
    rows = [{"number": "1", "label": "wash"}, {"number": "2", "label": "wash"}]
    assert _case_variants(rows) == []


def test_unlabelled_targets_are_listed() -> None:
    assert _unlabelled(HOUSELIGHTS) == ["506"]


def test_whitespace_only_labels_count_as_unlabelled() -> None:
    assert _unlabelled([{"number": "3", "label": "   "}]) == ["3"]


def test_blank_labels_are_not_duplicates_of_each_other() -> None:
    """Two unlabelled targets share "" - that is missing, not duplicated."""
    rows = [{"number": "3", "label": ""}, {"number": "33", "label": ""}]
    assert _duplicate_labels(rows) == []


def test_missing_label_key_is_tolerated() -> None:
    """Types without a label field must not crash the audit."""
    rows = [{"number": "1"}]
    assert _duplicate_labels(rows) == []
    assert _unlabelled(rows) == ["1"]

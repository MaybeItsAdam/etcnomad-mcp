"""Show-file auditing - mechanical checks over enumerated show data.

Everything here was found by hand in a real show and is tedious enough to miss:
seven effects all called "pulse", six houselight channels labelled three
different ways, a submaster called "inn wash". None of it breaks a show, and
all of it makes one harder to work with under pressure.

These are reports, not repairs. Nothing in this module writes to the console.
"""

from __future__ import annotations

from collections import defaultdict

from ..app import mcp
from ._common import ToolResult, guarded, success
from .inventory import TARGET_TYPES, _enumerate

#: Types where a repeated label means something was recorded twice. Patch is
#: absent by design: six channels of one wash sharing a name is normal, and
#: reporting it would bury the real findings.
DUPLICATE_TYPES = ("sub", "effect", "group", "preset", "macro", "cuelist")

#: Types where labels differing only by case are worth reporting. Patch *is*
#: included: "Houselights" next to "HOUSELIGHTS" is a genuine inconsistency,
#: and excluding patch wholesale missed exactly that on a real show.
CASE_VARIANT_TYPES = (*DUPLICATE_TYPES, "patch")

#: Types where a missing label is worth reporting. Patch is absent: unlabelled
#: channels are the norm rather than a defect.
UNLABELLED_TYPES = DUPLICATE_TYPES

#: Every type the audit enumerates, in a stable order.
LABELLED_TYPES = (*DUPLICATE_TYPES, "patch")


def _duplicate_labels(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Find labels used by more than one target of the same type."""
    by_label: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        label = str(row.get("label") or "").strip()
        if label:
            by_label[label].append(str(row["number"]))
    return [
        {"label": label, "numbers": numbers}
        for label, numbers in sorted(by_label.items())
        if len(numbers) > 1
    ]


def _case_variants(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Find labels that differ only by case or surrounding whitespace.

    ``Houselights`` and ``HOUSELIGHTS`` in one show is almost always accidental,
    and it defeats searching for either.
    """
    by_folded: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        label = str(row.get("label") or "").strip()
        if label:
            by_folded[label.casefold()].add(label)
    return [{"variants": sorted(variants)} for variants in by_folded.values() if len(variants) > 1]


def _unlabelled(rows: list[dict[str, object]]) -> list[str]:
    """Targets that exist but carry no label."""
    return [str(row["number"]) for row in rows if not str(row.get("label") or "").strip()]


@mcp.tool()
@guarded("audit_show")
def audit_show() -> ToolResult:
    """Reports duplicate, inconsistent and missing labels across the show.

    Reads only - it never modifies anything. Enumerates each target type and
    reports:

    * duplicate labels within a type, which usually means something was
      re-recorded rather than edited
    * labels differing only by case, which defeats searching
    * targets with no label at all

    Returns a per-type breakdown plus a count of findings.
    """
    findings: dict[str, object] = {}
    unreachable: list[str] = []
    total = 0

    for friendly in LABELLED_TYPES:
        token = TARGET_TYPES.get(friendly, friendly)
        count, rows = _enumerate(token)
        if count is None:
            unreachable.append(friendly)
            continue
        if not rows:
            continue

        duplicates = _duplicate_labels(rows) if friendly in DUPLICATE_TYPES else []
        variants = _case_variants(rows) if friendly in CASE_VARIANT_TYPES else []
        blank = _unlabelled(rows) if friendly in UNLABELLED_TYPES else []
        if not (duplicates or variants or blank):
            continue

        findings[friendly] = {
            "duplicate_labels": duplicates,
            "case_variants": variants,
            "unlabelled": blank,
        }
        total += len(duplicates) + len(variants) + len(blank)

    if unreachable:
        detail = (
            f"{total} finding(s). No reply for: {', '.join(unreachable)} - that part of "
            "the show was not checked, so this is not a clean bill of health."
        )
    elif total:
        detail = f"{total} finding(s) across {len(findings)} target type(s)."
    else:
        detail = "No duplicate, inconsistent or missing labels found."

    return success(
        "audit_show",
        detail,
        findings=findings,
        finding_count=total,
        unreachable=unreachable,
    )

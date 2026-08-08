"""Enumeration of show data - the numbered ledger of what a show contains.

Eos exposes a uniform three-step protocol for every target type: ask for a
count, request each index from 0 to count-1, and receive one reply per record.
This module wraps that loop so a model can ask "what submasters exist?" and get
an answer, rather than having to infer it from a console screenshot.

Enumeration is a read: it never modifies the show. It is the prerequisite for
safe writes, because recording onto an occupied target silently replaces it.
"""

from __future__ import annotations

import time

from ..app import mcp
from ..osc.client import client
from ..state import snapshot, state, state_lock
from ._common import ToolResult, guarded, success

#: Target types Eos will enumerate, mapped to the token used in OSC addresses.
#: Cues are deliberately absent - they are per-cue-list and need a list number,
#: so they are reached through ``target_type="cue/<list>"``.
TARGET_TYPES: dict[str, str] = {
    "patch": "patch",
    "sub": "sub",
    "effect": "fx",
    "group": "group",
    "macro": "macro",
    "curve": "curve",
    "preset": "preset",
    "cuelist": "cuelist",
    "snapshot": "snap",
    "magicsheet": "ms",
    "pixelmap": "pixmap",
    "intensity_palette": "ip",
    "focus_palette": "fp",
    "color_palette": "cp",
    "beam_palette": "bp",
}

COUNT_TIMEOUT = 2.0
DETAIL_TIMEOUT = 6.0
POLL_INTERVAL = 0.05


def _resolve(target_type: str) -> str:
    """Map a friendly name to its OSC token, passing through raw tokens."""
    if target_type in TARGET_TYPES:
        return TARGET_TYPES[target_type]
    # Allow raw tokens and scoped forms such as "cue/1".
    return target_type


def _await_count(token: str) -> int | None:
    """Wait for Eos to report how many records of ``token`` exist."""
    deadline = time.monotonic() + COUNT_TIMEOUT
    while time.monotonic() < deadline:
        with state_lock:
            if token in state.target_counts:
                return state.target_counts[token]
        time.sleep(POLL_INTERVAL)
    return None


def _enumerate(token: str) -> tuple[int | None, list[dict[str, str]]]:
    """Run the count-then-index protocol for one target type."""
    # Drop any previous answer so a stale count cannot satisfy the wait below.
    with state_lock:
        state.target_counts.pop(token, None)
        state.show_targets.pop(token.split("/")[0], None)

    client.send(f"/eos/get/{token}/count")
    count = _await_count(token)
    if count is None:
        return None, []
    if count == 0:
        return 0, []

    for index in range(count):
        client.send(f"/eos/get/{token}/index/{index}")

    bucket_key = token.split("/")[0]
    deadline = time.monotonic() + DETAIL_TIMEOUT
    while time.monotonic() < deadline:
        with state_lock:
            got = len(state.show_targets.get(bucket_key, {}))
        if got >= count:
            break
        time.sleep(POLL_INTERVAL)

    records = snapshot().show_targets.get(bucket_key, {})
    rows = [
        {"number": rec.number, "label": rec.label}
        for rec in sorted(records.values(), key=lambda r: _sort_key(r.number))
    ]
    return count, rows


def _sort_key(number: str) -> tuple[float, str]:
    """Order target numbers numerically where possible, textually otherwise."""
    head = number.split("/")[0]
    try:
        return (float(head), number)
    except ValueError:
        return (float("inf"), number)


@mcp.tool()
@guarded("list_show_targets")
def list_show_targets(target_type: str) -> ToolResult:
    """Lists every record of one target type, with its number and label.

    Use this before recording anything. Eos overwrites an occupied target
    without warning, so "is sub 5 free?" must be answered from the console
    rather than assumed.

    Args:
        target_type: One of patch, sub, effect, group, macro, curve, preset,
            cuelist, snapshot, magicsheet, pixelmap, intensity_palette,
            focus_palette, color_palette, beam_palette. Cues are per list, so
            pass ``"cue/1"`` for cue list 1.
    """
    token = _resolve(target_type)
    count, rows = _enumerate(token)

    if count is None:
        return success(
            "list_show_targets",
            f"Asked Eos for the {target_type} count but it did not reply within "
            f"{COUNT_TIMEOUT}s. Check get_connection_health - without a reply this "
            "says nothing about whether records exist.",
            target_type=target_type,
            known=False,
            count=None,
            targets=[],
        )

    detail = f"{count} {target_type} record(s)."
    if len(rows) < count:
        detail += f" Only {len(rows)} arrived within {DETAIL_TIMEOUT}s - the list is incomplete."

    return success(
        "list_show_targets",
        detail,
        target_type=target_type,
        known=True,
        count=count,
        returned=len(rows),
        targets=rows,
    )


@mcp.tool()
@guarded("get_show_inventory")
def get_show_inventory() -> ToolResult:
    """Enumerates every target type at once - the full ledger of the show.

    Slower than a single ``list_show_targets`` because it walks each type in
    turn. Use it to audit a show file, or when you need to know what is free
    before writing.
    """
    inventory: dict[str, object] = {}
    unreachable: list[str] = []

    for friendly, token in TARGET_TYPES.items():
        count, rows = _enumerate(token)
        if count is None:
            unreachable.append(friendly)
            continue
        inventory[friendly] = {"count": count, "targets": rows}

    populated = {k: v for k, v in inventory.items() if isinstance(v, dict) and v["count"]}
    detail = f"Enumerated {len(inventory)} target types; {len(populated)} contain records."
    if unreachable:
        detail += f" No reply for: {', '.join(unreachable)}."

    return success(
        "get_show_inventory",
        detail,
        inventory=inventory,
        unreachable=unreachable,
    )

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
#: How many index requests to send before pausing, and how long to pause.
REQUEST_CHUNK = 50
CHUNK_PAUSE = 0.02


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


def _request_all(token: str, count: int) -> None:
    """Request every record, in paced chunks.

    A tight loop of thousands of datagrams is a good way to have the console,
    the loopback buffer, or an intervening switch drop some of them. Pausing
    between chunks costs milliseconds and makes a large show enumerate
    reliably rather than mostly.
    """
    for start in range(0, count, REQUEST_CHUNK):
        for index in range(start, min(start + REQUEST_CHUNK, count)):
            client.send(f"/eos/get/{token}/index/{index}")
        if start + REQUEST_CHUNK < count:
            time.sleep(CHUNK_PAUSE)


def _await_records(bucket_key: str, count: int) -> int:
    """Wait for ``count`` records to arrive, returning how many did."""
    deadline = time.monotonic() + DETAIL_TIMEOUT
    got = 0
    while time.monotonic() < deadline:
        with state_lock:
            got = len(state.show_targets.get(bucket_key, {}))
        if got >= count:
            break
        time.sleep(POLL_INTERVAL)
    return got


def _enumerate(token: str) -> tuple[int | None, list[dict[str, object]]]:
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

    bucket_key = token.split("/")[0]
    _request_all(token, count)
    got = _await_records(bucket_key, count)

    # UDP drops silently, and a partial ledger reads like a small show rather
    # than a lossy link. One retry costs little and recovers the usual case.
    if got < count:
        _request_all(token, count)
        _await_records(bucket_key, count)

    records = snapshot().show_targets.get(bucket_key, {})
    rows: list[dict[str, object]] = []
    for rec in sorted(records.values(), key=lambda r: _sort_key(r.number)):
        row: dict[str, object] = {"number": rec.number, "label": rec.label}
        row.update(rec.extra)
        rows.append(row)
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

    # Cues are the largest part of most shows and are addressed per cue list,
    # so they cannot be walked like the flat types above. Omitting them made
    # the "full ledger" quietly exclude most of the show.
    cue_lists = inventory.get("cuelist")
    if isinstance(cue_lists, dict):
        cues: dict[str, object] = {}
        for row in cue_lists["targets"]:
            list_number = str(row["number"])
            count, rows = _enumerate(f"cue/{list_number}")
            if count is None:
                unreachable.append(f"cue list {list_number}")
                continue
            cues[list_number] = {"count": count, "targets": rows}
        if cues:
            inventory["cue"] = cues

    # "cue" is nested per cue list and carries no top-level count of its own.
    populated = {k: v for k, v in inventory.items() if isinstance(v, dict) and v.get("count")}
    detail = f"Enumerated {len(inventory)} target types; {len(populated)} contain records."
    if unreachable:
        detail += f" No reply for: {', '.join(unreachable)}."

    return success(
        "get_show_inventory",
        detail,
        inventory=inventory,
        unreachable=unreachable,
    )

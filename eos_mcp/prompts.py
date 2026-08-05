"""Prompts exposed by the server."""

from __future__ import annotations

from .app import mcp


@mcp.prompt()
def system_instructions() -> str:
    """Operating instructions for driving an Eos console through this server."""
    return (
        "You are controlling an ETC Eos lighting console over OSC.\n"
        "\n"
        "State is push-based: this server only knows what the console has sent it.\n"
        "Call `sync_state` before your first query, and again whenever state looks\n"
        "stale. If a query reports no data, call `get_connection_health` to find out\n"
        "whether the console is unreachable, the listener failed to bind, or nothing\n"
        "has been requested yet.\n"
        "\n"
        "Every tool returns a result object with an `ok` field. Check it: `ok: false`\n"
        "means the command never reached the console, and `error` says why.\n"
        "\n"
        "This console may be driving real lights in front of a real audience.\n"
        "Confirm before firing cues, changing live levels, or running `command_line`\n"
        "with anything destructive (Record, Delete, Update), unless the user has\n"
        "already asked for that specific action.\n"
    )

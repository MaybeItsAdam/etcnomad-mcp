"""OSC cue list banks - the paged cue view Eos can push to a client."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..app import mcp
from ..osc import address as addr
from ._common import BankIndex, TargetNumber, ToolResult, guarded, send


@mcp.tool()
@guarded("config_cue_list_bank")
def config_cue_list_bank(
    index: BankIndex,
    list_num: TargetNumber,
    prev: Annotated[int, Field(ge=0)] = 2,
    pending: Annotated[int, Field(ge=0)] = 6,
) -> ToolResult:
    """Configures a cue list bank so Eos starts publishing that list.

    Args:
        index: Bank index to configure.
        list_num: Cue list to show in the bank.
        prev: How many already-played cues to include.
        pending: How many upcoming cues to include.
    """
    return send(
        f"/eos/cuelist/{index}/config/{list_num}/{prev}/{pending}",
        action="config_cue_list_bank",
        detail=f"Configured cue list bank {index} for list {list_num}",
    )


@mcp.tool()
@guarded("page_cue_list_bank")
def page_cue_list_bank(index: BankIndex, delta: int) -> ToolResult:
    """Pages a cue list bank.

    Args:
        index: Bank index.
        delta: Pages to move. Positive pages forward, negative pages back.
    """
    return send(
        f"/eos/cuelist/{index}/page/{delta}",
        action="page_cue_list_bank",
        detail=f"Paged cue list bank {index} by {delta}",
    )


@mcp.tool()
@guarded("select_cue_list_bank_cue")
def select_cue_list_bank_cue(index: BankIndex, cue: str) -> ToolResult:
    """Jumps a cue list bank to a specific cue.

    Args:
        index: Bank index.
        cue: Cue number. Point cues such as "1.5" are supported.
    """
    cue_num = addr.cue_number(cue, "cue")
    return send(
        f"/eos/cuelist/{index}/select/{cue_num}",
        action="select_cue_list_bank_cue",
        detail=f"Cue list bank {index} jumped to cue {cue_num}",
    )


@mcp.tool()
@guarded("reset_cue_list_bank")
def reset_cue_list_bank(index: BankIndex) -> ToolResult:
    """Resets a cue list bank."""
    return send(
        f"/eos/cuelist/{index}/reset",
        action="reset_cue_list_bank",
        detail=f"Reset cue list bank {index}",
    )

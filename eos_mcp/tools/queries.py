"""Read-only queries against the state the console has pushed to us.

None of these talk to the console; they report what the OSC listener has
received. `sync_state` is the exception - it asks Eos to re-send everything and
waits for a reply. Fields are ``None`` when the console has not reported them
yet, which is deliberately distinct from a real value.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from pathlib import PurePosixPath

from ..app import mcp
from ..config import config
from ..osc.client import client
from ..osc.listener import listener
from ..state import snapshot, state, state_lock
from ._common import BankIndex, TargetNumber, ToolResult, guarded, success

#: How long `sync_state` waits for the console to answer.
#:
#: 1.5s was too short against a real console: Eos was replying, but late, so
#: sync_state reported failure while enumeration - which waits longer - worked
#: first time. A sync that gives up early is worse than a slow one, because it
#: reports a working link as dead.
SYNC_TIMEOUT = 4.0
#: How often it re-checks while waiting.
SYNC_POLL_INTERVAL = 0.05

#: Size of the fader and direct select banks sync_state creates. Ten covers a
#: standard console fader page; configure_fader_bank overrides it.
DEFAULT_FADER_COUNT = 10
DEFAULT_DS_COUNT = 10


def _age(last_update: float | None) -> float | None:
    """Seconds since a monotonic timestamp, or ``None`` if never set."""
    if last_update is None:
        return None
    return round(time.monotonic() - last_update, 3)


def _name_from_path(show_path: str | None) -> str | None:
    """Derive a show name from its file path, dropping directories and suffix."""
    if not show_path:
        return None
    name = PurePosixPath(show_path.replace("\\", "/")).name
    return name.rsplit(".", 1)[0] or None


def _local_address() -> str | None:
    """This machine's outbound IPv4 address, or ``None`` if it cannot be found.

    Used to tell the user the exact value to type into the console rather than
    "use your LAN address". Opening a UDP socket to an unroutable address makes
    the OS pick the interface it would send from; nothing is transmitted.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # TEST-NET-1 (RFC 5737). Reserved for documentation, never routed.
            sock.connect(("192.0.2.1", 9))
            address = str(sock.getsockname()[0])
        finally:
            sock.close()
    except OSError:
        return None
    return None if address.startswith("127.") else address


def _tx_address_hint() -> str:
    """Name the address the console should transmit to, if it can be determined."""
    address = _local_address()
    if not address:
        return ""
    return f" This machine is currently {address}, so that is the value to enter."


def _sender_is_console(last_sender: str | None) -> bool:
    """Whether the last datagram came from the address commands are sent to."""
    if not last_sender:
        return False
    return last_sender.rsplit(":", 1)[0] == config.eos_ip


def _sender_note() -> str:
    """Explain the benign case where sender and console address legitimately differ.

    With Eos on this machine, commands are addressed to loopback while Eos
    transmits from its LAN interface - because it does not bind loopback for
    transmit. The two addresses then never match, and that is correct.
    """
    try:
        console_is_local = ipaddress.ip_address(config.eos_ip).is_loopback
    except ValueError:
        return ""
    if not console_is_local:
        return ""
    return (
        " Note: with EOS_IP set to loopback and Eos on this machine, its replies "
        "arrive from the LAN interface, so a differing address here is expected."
    )


@mcp.tool()
@guarded("get_active_cue")
def get_active_cue() -> ToolResult:
    """Returns the cue currently running on the master playback."""
    s = snapshot()
    if s.active_cue_number is None:
        return success(
            "get_active_cue",
            "No active cue reported yet. Call sync_state first.",
            known=False,
        )
    return success(
        "get_active_cue",
        f"Active cue {s.active_cue_list}/{s.active_cue_number} "
        f"({s.active_cue_percent * 100:.0f}%) '{s.active_cue_text}'",
        known=True,
        cue_list=s.active_cue_list,
        cue_number=s.active_cue_number,
        percent_complete=round(s.active_cue_percent * 100, 1),
        label=s.active_cue_text,
        age_seconds=_age(s.last_update),
    )


@mcp.tool()
@guarded("get_pending_cue")
def get_pending_cue() -> ToolResult:
    """Returns the cue that will run on the next Go."""
    s = snapshot()
    if s.pending_cue_number is None:
        return success(
            "get_pending_cue",
            "No pending cue reported yet. Call sync_state first.",
            known=False,
        )
    return success(
        "get_pending_cue",
        f"Pending cue {s.pending_cue_list}/{s.pending_cue_number} '{s.pending_cue_text}'",
        known=True,
        cue_list=s.pending_cue_list,
        cue_number=s.pending_cue_number,
        label=s.pending_cue_text,
    )


@mcp.tool()
@guarded("get_live_blind_state")
def get_live_blind_state() -> ToolResult:
    """Returns whether the console is in Live or Blind.

    Reports "unknown" until the console has told us. Do not assume Live.
    """
    s = snapshot()
    return success(
        "get_live_blind_state",
        f"Console state: {s.live_blind_label}",
        known=s.live_blind_state is not None,
        state=s.live_blind_label,
    )


@mcp.tool()
@guarded("get_command_line")
def get_command_line() -> ToolResult:
    """Returns the text currently on the console's command line."""
    s = snapshot()
    return success(
        "get_command_line",
        f"Command line: {s.command_line}",
        command_line=s.command_line,
    )


@mcp.tool()
@guarded("get_selection")
def get_selection() -> ToolResult:
    """Returns the channels currently selected on the console."""
    s = snapshot()
    return success(
        "get_selection",
        f"Selected channels: {s.active_channels or '(none)'}",
        channels=s.active_channels,
    )


@mcp.tool()
@guarded("get_faders")
def get_faders(bank: BankIndex) -> ToolResult:
    """Returns every known fader in a bank.

    Args:
        bank: Fader bank index. Banks are populated by `sync_state`.
    """
    s = snapshot()
    fader_bank = s.faders.get(bank)
    if fader_bank is None:
        return success(
            "get_faders",
            f"No data for fader bank {bank}. Call sync_state first.",
            known=False,
            bank=bank,
            faders=[],
        )
    faders = [
        {"index": idx, "label": f.label, "level": round(f.level, 4)}
        for idx, f in sorted(fader_bank.faders.items())
    ]
    listing = "\n".join(f"  Fader {f['index']}: {f['label']} = {f['level']:.2f}" for f in faders)
    return success(
        "get_faders",
        f"Bank {bank} ({fader_bank.bank_label}):\n" + (listing or "  No faders populated."),
        known=True,
        bank=bank,
        bank_label=fader_bank.bank_label,
        faders=faders,
    )


@mcp.tool()
@guarded("get_direct_selects")
def get_direct_selects(bank: BankIndex) -> ToolResult:
    """Returns every known button in a direct select bank.

    Args:
        bank: Direct select bank index.
    """
    s = snapshot()
    ds_bank = s.direct_selects.get(bank)
    if ds_bank is None:
        return success(
            "get_direct_selects",
            f"No data for direct select bank {bank}. Call sync_state first.",
            known=False,
            bank=bank,
            buttons=[],
        )
    buttons = [{"index": idx, "label": label} for idx, label in sorted(ds_bank.buttons.items())]
    listing = "\n".join(f"  Btn {b['index']}: {b['label']}" for b in buttons)
    return success(
        "get_direct_selects",
        f"DS bank {bank} ({ds_bank.label}):\n" + (listing or "  No buttons populated."),
        known=True,
        bank=bank,
        bank_label=ds_bank.label,
        buttons=buttons,
    )


@mcp.tool()
@guarded("get_system_state")
def get_system_state() -> ToolResult:
    """Returns aggregate console state: Live/Blind, wheel mode, and position data."""
    s = snapshot()
    lines = [f"Console state: {s.live_blind_label}"]
    if s.wheel_mode is not None:
        lines.append(f"Wheel mode: {s.wheel_mode}")
    if s.pantilt:
        lines.append(f"Pan/tilt: {s.pantilt}")
    if s.xyz:
        lines.append(f"XYZ: {s.xyz}")

    return success(
        "get_system_state",
        "\n".join(lines),
        state=s.live_blind_label,
        wheel_mode=s.wheel_mode,
        pantilt=s.pantilt,
        xyz=s.xyz,
        has_data=s.has_data,
    )


@mcp.tool()
@guarded("get_connection_health")
def get_connection_health() -> ToolResult:
    """Reports whether this server can reach the console and hear it replying.

    Call this first when a query says it has no data - it distinguishes "the
    console has not been asked yet" from "the listener never bound" or "the
    console is not sending".

    If the listener is down, this retries the bind before reporting. The port
    is usually held by another instance of this server, so the bind can start
    succeeding long after startup - without a retry the listener would stay
    dead for the life of the process even once the port was free.
    """
    rebound = False
    if not listener.is_running:
        rebound = listener.start()

    s = snapshot()
    age = _age(s.last_update)

    if listener.bind_error:
        detail = f"OSC listener is NOT running: {listener.bind_error}"
    elif rebound:
        detail = (
            f"OSC listener was down and has just rebound to {listener.bound_address}. "
            "Call sync_state to repopulate console state."
        )
    elif not listener.is_running:
        detail = "OSC listener has not been started."
    elif age is None:
        detail = (
            f"Listening on {listener.bound_address} but the console has sent nothing yet. "
            "Call sync_state. If it stays silent, the console is not transmitting, and "
            "only a human at the console can fix it - these are show-file settings under "
            "Setup > System > Show Control > OSC, not something this server can change. "
            "Ask the user to check, in this order: (1) OSC UDP TX IP Address is the LAN "
            "address of the machine running this server, and NOT 127.0.0.1 - Eos does "
            "not bind its transmit socket to loopback, so a loopback address sends to "
            "nobody even on a single machine, while TX still reads as enabled and "
            f"commands still land.{_tx_address_hint()} Then (2) OSC TX is enabled; "
            f"(3) OSC UDP TX Port matches {config.port_rx}. Note this address changes "
            "when the machine joins a different network, and these are show-file "
            "settings, so loading or reloading a show reverts them."
        )
    elif _sender_is_console(s.last_sender):
        detail = f"Healthy. Last OSC message from the console ({s.last_sender}) {age:.1f}s ago."
    else:
        detail = (
            f"Last OSC message came from {s.last_sender} {age:.1f}s ago, which is not the "
            f"configured console address {config.eos_ip}. Any process can send to this "
            f"port, so traffic alone is not proof the console is reachable.{_sender_note()}"
        )

    return success(
        "get_connection_health",
        detail,
        listener_running=listener.is_running,
        listener_bound_to=listener.bound_address,
        bind_error=listener.bind_error,
        command_target=client.target,
        seconds_since_last_message=age,
        last_sender=s.last_sender,
        has_data=s.has_data,
    )


@mcp.tool()
@guarded("get_channel_parameters")
def get_channel_parameters(channel: TargetNumber) -> ToolResult:
    """Reports what a channel is currently doing - every live parameter value.

    This is the only way to see actual output. Enumeration says what has been
    *assigned* to a channel; this says what the channel is doing as a result,
    which is how you tell a running effect from one that was recorded and does
    nothing.

    Selecting the channel is how Eos is asked, so this changes the console's
    current selection as a side effect.

    Args:
        channel: The channel to inspect.
    """
    with state_lock:
        before_seq = state.wheels_seq
        state.wheels.clear()

    client.send(f"/eos/chan/{channel}")

    deadline = time.monotonic() + SYNC_TIMEOUT
    while time.monotonic() < deadline:
        with state_lock:
            if state.wheels_seq != before_seq and state.wheels:
                break
        time.sleep(SYNC_POLL_INTERVAL)

    s = snapshot()
    if not s.wheels:
        return success(
            "get_channel_parameters",
            f"Selected channel {channel} but the console reported no parameters within "
            f"{SYNC_TIMEOUT}s. Check get_connection_health - this says nothing about "
            "what the channel is doing.",
            channel=channel,
            known=False,
            parameters=[],
        )

    parameters = [
        {"name": w.name, "level": w.level, "group": w.group}
        for _, w in sorted(s.wheels.items())
        if w.name
    ]
    summary = ", ".join(f"{p['name']} {p['level']:g}" for p in parameters)
    return success(
        "get_channel_parameters",
        f"Channel {channel}: {summary}",
        channel=channel,
        known=True,
        selection=s.active_channels,
        parameters=parameters,
    )


@mcp.tool()
@guarded("get_show_info")
def get_show_info() -> ToolResult:
    """Reports which show is loaded, where it lives, and the Eos version.

    Worth checking before auditing or writing anything. A console can hold a
    different show than the one you have open on disk, and every conclusion
    drawn from the wrong show is wrong.
    """
    client.send("/eos/get/show/path")
    client.send("/eos/get/version")

    deadline = time.monotonic() + SYNC_TIMEOUT
    while time.monotonic() < deadline:
        s = snapshot()
        if s.show_name is not None or s.show_path is not None:
            break
        time.sleep(SYNC_POLL_INTERVAL)

    s = snapshot()
    if s.show_name is None and s.show_path is None:
        return success(
            "get_show_info",
            f"The console did not report a show within {SYNC_TIMEOUT}s. Check "
            "get_connection_health - do not assume which show is loaded.",
            known=False,
            show_name=None,
            show_path=None,
            eos_version=s.eos_version,
        )

    # Eos does not always push /eos/out/show/name, but the path carries the
    # same name. Reporting "unnamed" while holding the filename is unhelpful.
    name = s.show_name or _name_from_path(s.show_path)

    detail = f"Show: {name or 'unnamed'}"
    if s.show_path:
        detail += f" ({s.show_path})"
    detail += (
        ". Whether there are unsaved changes cannot be read over OSC - assume there are, "
        "and note that show-file settings, including OSC transmit, are lost on restart "
        "if the show has not been saved since they were set."
    )

    return success(
        "get_show_info",
        detail,
        known=True,
        show_name=name,
        show_name_reported_by_console=s.show_name,
        show_path=s.show_path,
        last_save_seen=s.show_saved,
        eos_version=s.eos_version,
    )


@mcp.tool()
@guarded("sync_state")
def sync_state() -> ToolResult:
    """Asks Eos to re-send its current status, and waits for a reply.

    Call this once at the start of a session, and again if state looks stale.
    Nothing else populates the cue, fader, or direct select data.
    """
    with state_lock:
        before = state.last_update

    requests = [
        "/eos/get/cue/active",
        "/eos/get/cue/pending",
        "/eos/get/version",
        "/eos/get/cmd",
        "/eos/get/setup",
        # Fader and direct select banks must be *created* before Eos sends any
        # labels or levels for them - the count is not optional. Requesting
        # ".../config" with no count creates nothing, so these stayed empty.
        f"/eos/fader/1/config/{DEFAULT_FADER_COUNT}",
        f"/eos/ds/1/config/sub/{DEFAULT_DS_COUNT}",
    ]
    # Without this, Eos answers one-shot requests but never pushes anything
    # else - selection, live/blind and fader config all stay empty no matter
    # how often they are asked for. It must be sent before the requests below
    # so their replies are not the only thing we ever hear.
    client.send("/eos/subscribe", 1)
    for address in requests:
        client.send(address)

    # Wait for something to arrive that is newer than what we already had, so a
    # previously-populated state cannot make an unresponsive console look healthy.
    deadline = time.monotonic() + SYNC_TIMEOUT
    responded = False
    while time.monotonic() < deadline:
        with state_lock:
            responded = state.last_update is not None and state.last_update != before
        if responded:
            break
        time.sleep(SYNC_POLL_INTERVAL)

    if responded:
        elapsed = round(time.monotonic() - (deadline - SYNC_TIMEOUT), 2)
        return success(
            "sync_state",
            f"Synchronisation complete - the console responded in {elapsed}s and state "
            "is populated.",
            responded=True,
            seconds_to_respond=elapsed,
            requests_sent=len(requests),
        )
    return success(
        "sync_state",
        f"Sent {len(requests)} requests to {client.target} but the console did not reply "
        f"within {SYNC_TIMEOUT}s. It may be unreachable, OSC TX may be disabled, or the "
        "console's OSC UDP TX IP Address may be blank or pointing at another machine. "
        "Call get_connection_health for details, and do not trust state until it responds.",
        responded=False,
        requests_sent=len(requests),
    )

"""Inbound OSC listener.

Eos pushes status updates to the port configured as its "OSC UDP TX Port"; this
module receives them and folds them into :mod:`eos_mcp.state`.

Two details are load-bearing:

* python-osc matches a registered address containing ``*`` with
  ``addr.replace("*", ".*?")``, which crosses ``/``. So ``/eos/out/fader/*``
  also receives ``/eos/out/fader/1/2`` and ``/eos/out/fader/1/2/name``. Each
  handler therefore re-checks the address against its own anchored regex and
  ignores anything that is not exactly its shape.
* Cue numbers may be point cues (``1.5``), so the cue regexes accept a decimal
  part. Requiring integers silently drops updates on most real show files.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from typing import Any

from pythonosc import dispatcher, osc_server

from ..config import EosConfig, config
from ..logging_setup import get_logger
from ..state import DirectSelectBank, Fader, FaderBank, ShowTarget, state, state_lock

logger = get_logger(__name__)

# --- OSC address regexes (anchored, named numeric segments) --------------

_CUE = r"\d+(?:\.\d+)?"

RE_ACTIVE_CUE = re.compile(rf"/eos/out/active/cue/(?P<list>\d+)/(?P<cue>{_CUE})")
RE_PENDING_CUE = re.compile(rf"/eos/out/pending/cue/(?P<list>\d+)/(?P<cue>{_CUE})")
RE_FADER_BANK = re.compile(r"/eos/out/fader/(?P<bank>\d+)")
RE_FADER_LEVEL = re.compile(r"/eos/out/fader/(?P<bank>\d+)/(?P<fader>\d+)")
RE_FADER_NAME = re.compile(r"/eos/out/fader/(?P<bank>\d+)/(?P<fader>\d+)/name")
RE_DS_BANK = re.compile(r"/eos/out/ds/(?P<bank>\d+)")
RE_DS_BUTTON = re.compile(r"/eos/out/ds/(?P<bank>\d+)/(?P<button>\d+)")

# Replies to /eos/get/<type>/count. Cues nest under a list number
# (/eos/out/get/cue/1/count), so the middle segment is optional.
RE_GET_COUNT = re.compile(r"/eos/out/get/(?P<type>[a-z0-9]+)(?:/(?P<scope>[\d.]+))?/count")

# Replies to /eos/get/<type>/index/<n>. Everything between the type and "/list/"
# identifies the target, and its shape varies per type: a sub is "5", a cue is
# "1/2.5/0", a patch entry is "30/1". Capturing it whole keeps one handler
# correct for all of them rather than needing a regex per target type.
RE_GET_DETAIL = re.compile(
    r"/eos/out/get/(?P<type>[a-z0-9]+)/(?P<target>[\d./]+)/list/(?P<index>\d+)/(?P<count>\d+)"
)


#: Signature every OSC handler in this module shares.
OscHandler = Callable[..., None]


def _mark_update() -> None:
    """Record that the console just told us something. Caller holds the lock."""
    state.last_update = time.monotonic()


def _guard(handler: OscHandler) -> OscHandler:
    """Wrap a handler so one malformed packet cannot kill an update path.

    python-osc invokes handlers on the server thread; an escaping exception
    would be logged by the socketserver and the update lost. Catching here keeps
    the failure visible and scoped to a single message.
    """

    def wrapper(address: str, *args: object) -> None:
        try:
            handler(address, *args)
        except Exception:
            logger.exception("OSC handler failed for %s with args %r", address, args)

    wrapper.__name__ = getattr(handler, "__name__", "handler")
    wrapper.__doc__ = handler.__doc__
    return wrapper


# --- OSC handlers --------------------------------------------------------


@_guard
def handle_active_cue(address: str, *args: object) -> None:
    """Handles /eos/out/active/cue/<list>/<cue> (float percent argument)."""
    m = RE_ACTIVE_CUE.fullmatch(address)
    if not m:
        return
    percent = args[0] if args and isinstance(args[0], (int, float)) else 0.0
    with state_lock:
        state.active_cue_list = m.group("list")
        state.active_cue_number = m.group("cue")
        state.active_cue_percent = float(percent)
        _mark_update()


@_guard
def handle_active_cue_text(address: str, *args: object) -> None:
    """Handles /eos/out/active/cue/text (string argument)."""
    if not args:
        return
    with state_lock:
        state.active_cue_text = str(args[0])
        _mark_update()


@_guard
def handle_pending_cue(address: str, *args: object) -> None:
    """Handles /eos/out/pending/cue/<list>/<cue>."""
    m = RE_PENDING_CUE.fullmatch(address)
    if not m:
        return
    with state_lock:
        state.pending_cue_list = m.group("list")
        state.pending_cue_number = m.group("cue")
        _mark_update()


@_guard
def handle_pending_cue_text(address: str, *args: object) -> None:
    """Handles /eos/out/pending/cue/text (string argument)."""
    if not args:
        return
    with state_lock:
        state.pending_cue_text = str(args[0])
        _mark_update()


@_guard
def handle_live_blind(address: str, *args: object) -> None:
    """Handles /eos/out/event/state (0=Blind, 1=Live)."""
    if not args or not isinstance(args[0], (int, float, bool)):
        return
    with state_lock:
        state.live_blind_state = int(args[0])
        _mark_update()


@_guard
def handle_command_line(address: str, *args: object) -> None:
    """Handles /eos/out/cmd and /eos/out/user/<num>/cmd."""
    if not args:
        return
    with state_lock:
        state.command_line = str(args[0])
        _mark_update()


@_guard
def handle_active_chan(address: str, *args: object) -> None:
    """Handles /eos/out/active/chan."""
    if not args:
        return
    with state_lock:
        state.active_channels = str(args[0])
        _mark_update()


@_guard
def handle_fader_bank_label(address: str, *args: object) -> None:
    """Handles /eos/out/fader/<index> (bank label)."""
    m = RE_FADER_BANK.fullmatch(address)
    if not m or not args:
        return
    bank = int(m.group("bank"))
    with state_lock:
        state.faders.setdefault(bank, FaderBank()).bank_label = str(args[0])
        _mark_update()


@_guard
def handle_fader_level(address: str, *args: object) -> None:
    """Handles /eos/out/fader/<index>/<fader> (level)."""
    m = RE_FADER_LEVEL.fullmatch(address)
    if not m:
        return
    # Levels arrive as floats, but accept ints so a 0 or 1 is not dropped.
    if not args or isinstance(args[0], (str, bytes)) or not isinstance(args[0], (int, float)):
        return
    bank = int(m.group("bank"))
    fader = int(m.group("fader"))
    with state_lock:
        bank_obj = state.faders.setdefault(bank, FaderBank())
        bank_obj.faders.setdefault(fader, Fader()).level = float(args[0])
        _mark_update()


@_guard
def handle_fader_label(address: str, *args: object) -> None:
    """Handles /eos/out/fader/<index>/<fader>/name."""
    m = RE_FADER_NAME.fullmatch(address)
    if not m or not args:
        return
    bank = int(m.group("bank"))
    fader = int(m.group("fader"))
    with state_lock:
        bank_obj = state.faders.setdefault(bank, FaderBank())
        bank_obj.faders.setdefault(fader, Fader()).label = str(args[0])
        _mark_update()


@_guard
def handle_ds_bank_label(address: str, *args: object) -> None:
    """Handles /eos/out/ds/<index>."""
    m = RE_DS_BANK.fullmatch(address)
    if not m or not args:
        return
    bank = int(m.group("bank"))
    with state_lock:
        state.direct_selects.setdefault(bank, DirectSelectBank()).label = str(args[0])
        _mark_update()


@_guard
def handle_ds_button_label(address: str, *args: object) -> None:
    """Handles /eos/out/ds/<index>/<button>."""
    m = RE_DS_BUTTON.fullmatch(address)
    if not m or not args:
        return
    bank = int(m.group("bank"))
    btn = int(m.group("button"))
    with state_lock:
        state.direct_selects.setdefault(bank, DirectSelectBank()).buttons[btn] = str(args[0])
        _mark_update()


@_guard
def handle_wheel_mode(address: str, *args: object) -> None:
    """Handles /eos/out/wheel."""
    if not args:
        return
    with state_lock:
        state.wheel_mode = args[0]
        _mark_update()


@_guard
def handle_pantilt(address: str, *args: object) -> None:
    """Handles /eos/out/pantilt."""
    with state_lock:
        state.pantilt = [float(a) for a in args if isinstance(a, (int, float))]
        _mark_update()


@_guard
def handle_xyz(address: str, *args: object) -> None:
    """Handles /eos/out/xyz."""
    with state_lock:
        state.xyz = [float(a) for a in args if isinstance(a, (int, float))]
        _mark_update()


@_guard
def handle_get_count(address: str, *args: object) -> None:
    """Handles /eos/out/get/<type>[/<scope>]/count (uint32 argument)."""
    m = RE_GET_COUNT.fullmatch(address)
    if not m or not args or not isinstance(args[0], (int, float)):
        return
    key = m.group("type")
    if m.group("scope") is not None:
        key = f"{key}/{m.group('scope')}"
    with state_lock:
        state.target_counts[key] = int(args[0])
        _mark_update()


@_guard
def handle_get_detail(address: str, *args: object) -> None:
    """Handles /eos/out/get/<type>/<target>/list/<index>/<count>.

    Eos sends the record in several packets; only the first carries the label,
    so a later packet must not overwrite a label already captured. Arguments are
    positional: 0 is the list index, 1 the UID, 2 the label.
    """
    m = RE_GET_DETAIL.fullmatch(address)
    if not m:
        return
    target_type = m.group("type")
    number = m.group("target").rstrip("/")
    uid = str(args[1]) if len(args) > 1 and isinstance(args[1], str) else ""
    label = str(args[2]) if len(args) > 2 and isinstance(args[2], str) else ""

    with state_lock:
        bucket = state.show_targets.setdefault(target_type, {})
        record = bucket.get(number)
        if record is None:
            bucket[number] = ShowTarget(target_type, number, label, uid)
        else:
            # Later packets of the same record carry no label; keep the first.
            record.label = record.label or label
            record.uid = record.uid or uid
        _mark_update()


@_guard
def default_handler(address: str, *args: object) -> None:
    """Records liveness for messages we do not model, and logs them at DEBUG."""
    with state_lock:
        _mark_update()
    logger.debug("RX (unhandled) %s %r", address, args)


def build_dispatcher() -> dispatcher.Dispatcher:
    """Register every handler. Exposed separately so tests can drive it directly."""
    disp = dispatcher.Dispatcher()

    disp.map("/eos/out/active/cue/*/*", handle_active_cue)
    disp.map("/eos/out/active/cue/text", handle_active_cue_text)
    disp.map("/eos/out/pending/cue/*/*", handle_pending_cue)
    disp.map("/eos/out/pending/cue/text", handle_pending_cue_text)

    disp.map("/eos/out/event/state", handle_live_blind)
    disp.map("/eos/out/cmd", handle_command_line)
    disp.map("/eos/out/user/*/cmd", handle_command_line)
    disp.map("/eos/out/active/chan", handle_active_chan)
    disp.map("/eos/out/wheel", handle_wheel_mode)
    disp.map("/eos/out/pantilt", handle_pantilt)
    disp.map("/eos/out/xyz", handle_xyz)

    disp.map("/eos/out/fader/*", handle_fader_bank_label)
    disp.map("/eos/out/fader/*/*", handle_fader_level)
    disp.map("/eos/out/fader/*/*/name", handle_fader_label)

    disp.map("/eos/out/ds/*", handle_ds_bank_label)
    disp.map("/eos/out/ds/*/*", handle_ds_button_label)

    # python-osc's "*" crosses "/", so one pattern reaches every depth these
    # replies use; each handler re-checks with its anchored regex.
    disp.map("/eos/out/get/*", handle_get_count)
    disp.map("/eos/out/get/*", handle_get_detail)

    disp.set_default_handler(default_handler)
    return disp


class RecordingOSCUDPServer(osc_server.ThreadingOSCUDPServer):
    """An OSC server that records who sent each datagram.

    Without this the server knows only that *something* arrived on the port.
    Any local process can send there, so "we received a packet" was being
    reported as "the console is healthy" - which is exactly backwards for a
    tool whose job is telling you whether the console is reachable.

    ``verify_request`` runs for every datagram regardless of which handler
    ends up matching, so recording here cannot miss one.
    """

    def verify_request(self, request: Any, client_address: Any) -> bool:
        with state_lock:
            state.last_sender = f"{client_address[0]}:{client_address[1]}"
        return True


class OscListener:
    """Owns the UDP server thread that receives replies from Eos.

    A bind failure (usually the RX port already in use) is captured on
    :attr:`bind_error` rather than killing the thread silently, so
    ``get_connection_health`` can report a cause instead of the server merely
    looking idle.
    """

    def __init__(self, cfg: EosConfig | None = None) -> None:
        self._config = cfg or config
        self._server: osc_server.ThreadingOSCUDPServer | None = None
        self._thread: threading.Thread | None = None
        self.bind_error: str | None = None

    @property
    def config(self) -> EosConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def bound_address(self) -> str | None:
        """Actual ``host:port`` bound, or ``None`` if not listening."""
        if self._server is None:
            return None
        host, port = self._server.server_address[:2]
        if isinstance(host, bytes):
            host = host.decode("utf-8", errors="replace")
        return f"{host}:{port}"

    def start(self) -> bool:
        """Bind and serve on a daemon thread.

        Returns:
            ``True`` if the listener is now serving, ``False`` if binding failed
            (the reason is on :attr:`bind_error`).
        """
        if self.is_running:
            return True

        try:
            self._server = RecordingOSCUDPServer(
                (self._config.rx_host, self._config.port_rx), build_dispatcher()
            )
        except OSError as exc:
            self.bind_error = (
                f"Could not bind the OSC listener to {self._config.rx_target}: {exc}. "
                "Another process may already be using that port, or set EOS_PORT_RX "
                "to a free port and match it to the console's OSC UDP TX Port."
            )
            logger.error("%s", self.bind_error)
            self._server = None
            return False

        self.bind_error = None
        self._thread = threading.Thread(target=self._serve, name="eos-osc-listener", daemon=True)
        self._thread.start()
        logger.info("OSC listener bound to %s", self.bound_address)
        return True

    def _serve(self) -> None:
        assert self._server is not None
        try:
            self._server.serve_forever()
        except Exception:
            logger.exception("OSC listener thread stopped unexpectedly")

    def stop(self, timeout: float = 2.0) -> None:
        """Shut the server down and release the socket."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None


#: Process-wide listener, started by :func:`eos_mcp.server.run`.
listener = OscListener()

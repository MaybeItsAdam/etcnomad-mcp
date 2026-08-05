"""Outbound OSC client.

The underlying socket is created lazily so that importing the package never
performs network setup - a bad ``EOS_IP`` then surfaces as a structured tool
error instead of an import-time crash.
"""

from __future__ import annotations

import threading
from typing import Any

from pythonosc import udp_client

from ..config import EosConfig, config
from ..errors import EosSendError
from ..logging_setup import get_logger
from .address import validate_address

logger = get_logger(__name__)

#: Values python-osc can encode without a manual builder.
ArgValue = float | int | str | bool | bytes


class EosClient:
    """Sends validated OSC messages to an Eos console over UDP."""

    def __init__(self, cfg: EosConfig | None = None) -> None:
        self._config = cfg or config
        self._client: udp_client.SimpleUDPClient | None = None
        self._lock = threading.Lock()

    @property
    def config(self) -> EosConfig:
        return self._config

    @property
    def target(self) -> str:
        """The ``host:port`` commands are sent to."""
        return self._config.tx_target

    def _get_client(self) -> udp_client.SimpleUDPClient:
        """Create the UDP client on first use, then reuse it."""
        with self._lock:
            if self._client is None:
                try:
                    self._client = udp_client.SimpleUDPClient(
                        self._config.eos_ip, self._config.port_tx
                    )
                except OSError as exc:
                    raise EosSendError(
                        f"Could not open a UDP socket to {self.target}: {exc}"
                    ) from exc
                logger.info("OSC client ready, sending to %s", self.target)
            return self._client

    def send(self, address: str, args: ArgValue | list[ArgValue] | None = None) -> None:
        """Send one OSC message.

        Args:
            address: A fully-assembled OSC address, validated before sending.
            args: A single value, a list of values, or ``None`` for no arguments.

        Raises:
            EosValidationError: If the address is malformed.
            EosSendError: If the message could not be handed to the network stack.
        """
        validate_address(address)
        payload: Any = [] if args is None else args
        try:
            self._get_client().send_message(address, payload)
        except EosSendError:
            raise
        except OSError as exc:
            raise EosSendError(
                f"Failed to send {address} to {self.target}: {exc}. "
                "Check the console is reachable and OSC RX is enabled."
            ) from exc
        except Exception as exc:
            raise EosSendError(f"Failed to build OSC message for {address}: {exc}") from exc
        logger.debug("TX %s %r", address, payload)

    def close(self) -> None:
        """Release the socket. Mainly useful in tests."""
        with self._lock:
            closer = getattr(self._client, "close", None)
            if callable(closer):
                closer()
            self._client = None


#: Process-wide client used by the tool modules.
client = EosClient()

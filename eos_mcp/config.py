"""Network and logging configuration, read from the environment.

Values are validated on load so a typo surfaces as an actionable message at
startup rather than as an opaque socket error on the first tool call.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import EosConfigError

DEFAULT_EOS_IP = "127.0.0.1"
DEFAULT_PORT_TX = 8000
DEFAULT_PORT_RX = 8001
DEFAULT_RX_HOST = "0.0.0.0"
DEFAULT_LOG_LEVEL = "INFO"

_VALID_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


def _env_port(name: str, default: int) -> int:
    """Read a UDP port from the environment, validating it is in range."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        port = int(raw)
    except ValueError:
        raise EosConfigError(f"{name} must be an integer port number, got {raw!r}") from None
    if not 1 <= port <= 65535:
        raise EosConfigError(f"{name} must be between 1 and 65535, got {port}")
    return port


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


@dataclass(frozen=True)
class EosConfig:
    """Resolved configuration for talking to an Eos console."""

    eos_ip: str = DEFAULT_EOS_IP
    port_tx: int = DEFAULT_PORT_TX
    port_rx: int = DEFAULT_PORT_RX
    rx_host: str = DEFAULT_RX_HOST
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> EosConfig:
        """Build a config from ``EOS_*`` environment variables.

        Raises:
            EosConfigError: if a port is not an integer in 1-65535, the log level
                is unrecognised, or the console IP is blank.
        """
        eos_ip = _env_str("EOS_IP", DEFAULT_EOS_IP)
        if not eos_ip:
            raise EosConfigError("EOS_IP must not be empty")

        log_level = _env_str("EOS_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
        if log_level not in _VALID_LOG_LEVELS:
            raise EosConfigError(
                f"EOS_LOG_LEVEL must be one of {sorted(_VALID_LOG_LEVELS)}, got {log_level!r}"
            )

        return cls(
            eos_ip=eos_ip,
            port_tx=_env_port("EOS_PORT_TX", DEFAULT_PORT_TX),
            port_rx=_env_port("EOS_PORT_RX", DEFAULT_PORT_RX),
            rx_host=_env_str("EOS_RX_HOST", DEFAULT_RX_HOST),
            log_level=log_level,
        )

    @property
    def tx_target(self) -> str:
        """Human-readable ``host:port`` the server sends commands to."""
        return f"{self.eos_ip}:{self.port_tx}"

    @property
    def rx_target(self) -> str:
        """Human-readable ``host:port`` the server listens on."""
        return f"{self.rx_host}:{self.port_rx}"


config = EosConfig.from_env()

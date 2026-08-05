"""Exception types raised inside the package.

Tools never let these escape into the MCP layer; ``eos_mcp.tools._common.send``
converts them into structured error results instead.
"""

from __future__ import annotations


class EosError(Exception):
    """Base class for every error this package raises."""


class EosConfigError(EosError):
    """Raised when environment configuration is missing or out of range."""


class EosValidationError(EosError):
    """Raised when a tool argument cannot be safely placed in an OSC address."""


class EosSendError(EosError):
    """Raised when an OSC message could not be handed to the network stack."""

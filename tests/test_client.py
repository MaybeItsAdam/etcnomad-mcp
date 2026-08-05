"""Send path: validation, error translation, and lazy socket creation."""

from __future__ import annotations

import pytest

from eos_mcp.config import EosConfig
from eos_mcp.errors import EosSendError, EosValidationError
from eos_mcp.osc.client import EosClient

from .conftest import RecordingUDPClient


def test_send_passes_address_and_args(sent: RecordingUDPClient) -> None:
    from eos_mcp.osc.client import client

    client.send("/eos/at", 50.0)
    assert sent.messages == [("/eos/at", 50.0)]


def test_send_with_no_args_sends_empty_list(sent: RecordingUDPClient) -> None:
    from eos_mcp.osc.client import client

    client.send("/eos/reset")
    assert sent.messages == [("/eos/reset", [])]


def test_send_rejects_malformed_address(sent: RecordingUDPClient) -> None:
    from eos_mcp.osc.client import client

    with pytest.raises(EosValidationError):
        client.send("not-an-address", 1.0)
    assert sent.messages == []


def test_socket_error_becomes_eos_send_error(failing_send: RecordingUDPClient) -> None:
    from eos_mcp.osc.client import client

    with pytest.raises(EosSendError, match="Network is unreachable"):
        client.send("/eos/at", 50.0)


def test_send_error_names_the_target(failing_send: RecordingUDPClient) -> None:
    from eos_mcp.osc.client import client

    with pytest.raises(EosSendError, match=client.target):
        client.send("/eos/at", 50.0)


def test_no_socket_is_created_on_construction() -> None:
    """Importing the package must not touch the network."""
    fresh = EosClient(EosConfig(eos_ip="203.0.113.1", port_tx=8000))
    assert fresh._client is None
    assert fresh.target == "203.0.113.1:8000"


def test_client_is_reused_across_sends(sent: RecordingUDPClient) -> None:
    from eos_mcp.osc.client import client

    client.send("/eos/at", 1.0)
    client.send("/eos/at", 2.0)
    assert len(sent.messages) == 2

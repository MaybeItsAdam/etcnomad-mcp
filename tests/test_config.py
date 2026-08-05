"""Configuration is validated at load so typos surface with an actionable message."""

from __future__ import annotations

import pytest

from eos_mcp.config import EosConfig
from eos_mcp.errors import EosConfigError


def test_defaults_when_nothing_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("EOS_IP", "EOS_PORT_TX", "EOS_PORT_RX", "EOS_RX_HOST", "EOS_LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)
    cfg = EosConfig.from_env()
    assert cfg.eos_ip == "127.0.0.1"
    assert cfg.port_tx == 8000
    assert cfg.port_rx == 9001


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EOS_IP", "10.0.0.5")
    monkeypatch.setenv("EOS_PORT_TX", "8001")
    monkeypatch.setenv("EOS_LOG_LEVEL", "debug")
    cfg = EosConfig.from_env()
    assert cfg.eos_ip == "10.0.0.5"
    assert cfg.port_tx == 8001
    assert cfg.log_level == "DEBUG"


@pytest.mark.parametrize("value", ["not-a-port", "0", "65536", "-1", "80.5"])
def test_invalid_port_is_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("EOS_PORT_TX", value)
    with pytest.raises(EosConfigError, match="EOS_PORT_TX"):
        EosConfig.from_env()


def test_invalid_log_level_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EOS_LOG_LEVEL", "chatty")
    with pytest.raises(EosConfigError, match="EOS_LOG_LEVEL"):
        EosConfig.from_env()


def test_blank_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EOS_IP", "  ")
    monkeypatch.setenv("EOS_PORT_RX", "")
    cfg = EosConfig.from_env()
    assert cfg.eos_ip == "127.0.0.1"
    assert cfg.port_rx == 9001


def test_targets_are_human_readable() -> None:
    cfg = EosConfig(eos_ip="10.0.0.5", port_tx=8000, rx_host="0.0.0.0", port_rx=9001)
    assert cfg.tx_target == "10.0.0.5:8000"
    assert cfg.rx_target == "0.0.0.0:9001"

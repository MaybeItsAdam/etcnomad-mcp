"""Guard against reintroducing writes to stdout.

Under the stdio transport the MCP client parses stdout as a stream of JSON-RPC
frames. A `print()` anywhere in the package injects a non-JSON line into that
stream and corrupts the session, which is exactly the bug this rules out.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "eos_mcp"
SOURCE_FILES = sorted(PACKAGE_ROOT.rglob("*.py"))


def test_sources_were_found() -> None:
    assert SOURCE_FILES, "no package sources found - check PACKAGE_ROOT"


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_print_calls(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
    ]
    assert not offenders, (
        f"{path.relative_to(PACKAGE_ROOT.parent)} calls print() at line(s) {offenders}; "
        "use eos_mcp.logging_setup.get_logger instead - stdout carries the MCP protocol"
    )


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_writes_to_sys_stdout(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "stdout"
        and isinstance(node.value, ast.Name)
        and node.value.id == "sys"
    ]
    assert not offenders, (
        f"{path.relative_to(PACKAGE_ROOT.parent)} references sys.stdout at "
        f"line(s) {offenders}; stdout carries the MCP protocol"
    )

# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for mypy type verifier."""

from __future__ import annotations

from llm_cst_refactorer.type_verifier import verify_source


def test_verify_accepts_valid_annotations() -> None:
    source = """def add(a: int, b: int) -> int:
    return a + b
"""
    result = verify_source(source)
    assert result.ok, result.errors


def test_verify_rejects_type_contradiction() -> None:
    source = """def add(a: int, b: int) -> str:
    return a + b
"""
    result = verify_source(source)
    assert not result.ok
    assert result.errors

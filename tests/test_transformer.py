# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for CST AnnotationApplier."""

from __future__ import annotations

from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.transformer import apply_suggestion


def test_applies_types_and_docstring_preserving_comment() -> None:
    source = """def add(a, b):
    # sum them
    return a + b
"""
    suggestion = Suggestion(
        param_types={"a": "int", "b": "int"},
        return_type="int",
        docstring="Add two numbers.\n\nArgs:\n    a: First.\n    b: Second.\n\nReturns:\n    Sum.",
    )
    after = apply_suggestion(source, "add", suggestion)
    assert "def add(a: int, b: int) -> int:" in after
    assert '"""Add two numbers.' in after
    assert "# sum them" in after


def test_applies_method_without_annotating_self() -> None:
    source = """class Widget:
    def paint(self, color):
        return color
"""
    suggestion = Suggestion(
        param_types={"color": "str"},
        return_type="str",
        docstring="Paint the widget.",
    )
    after = apply_suggestion(source, "Widget.paint", suggestion)
    assert "def paint(self, color: str) -> str:" in after
    assert "Paint the widget." in after


def test_async_function() -> None:
    source = """async def load(path):
    return path
"""
    after = apply_suggestion(
        source,
        "load",
        Suggestion(param_types={"path": "str"}, return_type="str", docstring="Load."),
    )
    assert "async def load(path: str) -> str:" in after

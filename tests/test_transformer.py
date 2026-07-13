# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for CST AnnotationApplier."""

from __future__ import annotations

from llm_cst_refactorer.models import FieldSuggestion, Suggestion
from llm_cst_refactorer.transformer import apply_suggestion


def test_applies_types_and_docstring_preserving_comment() -> None:
    source = """def add(a, b):
    # sum them
    return a + b
"""
    suggestion = Suggestion(
        param_types={
            "a": FieldSuggestion(value="int", confidence=0.9),
            "b": FieldSuggestion(value="int", confidence=0.9),
        },
        return_type=FieldSuggestion(value="int", confidence=0.9),
        docstring=FieldSuggestion(
            value="Add two numbers.\n\nArgs:\n    a: First.\n    b: Second.\n\nReturns:\n    Sum.",
            confidence=0.8,
        ),
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
        param_types={"color": FieldSuggestion(value="str", confidence=0.9)},
        return_type=FieldSuggestion(value="str", confidence=0.9),
        docstring=FieldSuggestion(value="Paint the widget.", confidence=0.8),
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
        Suggestion(
            param_types={"path": FieldSuggestion(value="str", confidence=0.9)},
            return_type=FieldSuggestion(value="str", confidence=0.9),
            docstring=FieldSuggestion(value="Load.", confidence=0.8),
        ),
    )
    assert "async def load(path: str) -> str:" in after

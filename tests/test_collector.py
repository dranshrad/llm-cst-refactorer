# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for AnnotationCollector."""

from __future__ import annotations

from pathlib import Path

from llm_cst_refactorer.collector import collect_functions

FIXTURES = Path(__file__).parent / "fixtures"


def test_collects_missing_annotations_and_docstring() -> None:
    source = (FIXTURES / "missing_all.py").read_text(encoding="utf-8")
    collected = collect_functions(source, file_path="missing_all.py")
    assert len(collected) == 1
    ctx = collected[0].context
    assert ctx.qualified_name == "add"
    assert ctx.needs.needs_params
    assert ctx.needs.needs_return
    assert ctx.needs.needs_docstring
    assert ctx.missing_param_names == ["a", "b"]


def test_skips_complete_functions() -> None:
    source = (FIXTURES / "complete.py").read_text(encoding="utf-8")
    collected = collect_functions(source)
    assert collected == []


def test_methods_async_and_skip_marker() -> None:
    source = (FIXTURES / "methods_async.py").read_text(encoding="utf-8")
    collected = collect_functions(source)
    names = {c.context.qualified_name for c in collected}
    assert "Widget.paint" in names
    assert "load" in names
    assert "ignored" not in names
    paint = next(c.context for c in collected if c.context.qualified_name == "Widget.paint")
    assert paint.is_method
    assert "self" not in paint.missing_param_names
    assert paint.missing_param_names == ["color"]
    load = next(c.context for c in collected if c.context.qualified_name == "load")
    assert load.is_async


def test_types_only_and_docs_only() -> None:
    source = (FIXTURES / "missing_all.py").read_text(encoding="utf-8")
    types = collect_functions(source, types_only=True)
    assert types[0].context.needs.needs_docstring is False
    assert types[0].context.needs.needs_params is True
    docs = collect_functions(source, docs_only=True)
    assert docs[0].context.needs.needs_params is False
    assert docs[0].context.needs.needs_docstring is True


def test_preserves_comment_context_in_source() -> None:
    source = """def greet(name):
    # keep me
    return name
"""
    collected = collect_functions(source)
    assert "# keep me" in collected[0].context.function_source

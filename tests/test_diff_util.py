# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for diff utilities."""

from __future__ import annotations

from llm_cst_refactorer.diff_util import colorize_diff, format_file_diff, unified_diff_text


def test_unified_diff_contains_changes() -> None:
    before = "a = 1\n"
    after = "a = 2\n"
    diff = unified_diff_text(before, after, fromfile="a/x.py", tofile="b/x.py")
    assert "-a = 1" in diff
    assert "+a = 2" in diff


def test_colorize_respects_no_color(monkeypatch: object) -> None:
    monkeypatch.setenv("NO_COLOR", "1")  # type: ignore[attr-defined]
    raw = unified_diff_text("a\n", "b\n", fromfile="a/f.py", tofile="b/f.py")
    colored = colorize_diff(raw, color=True)
    assert "\033[31m" in colored or "\033[32m" in colored
    plain = colorize_diff(raw, color=False)
    assert "\033[" not in plain


def test_format_file_diff() -> None:
    text = format_file_diff("pkg/mod.py", "x = 1\n", "x = 2\n", color=False)
    assert "a/pkg/mod.py" in text
    assert "b/pkg/mod.py" in text

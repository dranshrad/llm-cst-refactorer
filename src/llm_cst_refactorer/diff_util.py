# SPDX-License-Identifier: AGPL-3.0-or-later
"""Git-style unified diffs with optional ANSI color for dry-run previews."""

from __future__ import annotations

import difflib
import os
import sys


class _Colors:
    RED = "\033[31m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    RESET = "\033[0m"


def _use_color(stream: object | None = None) -> bool:
    if os.getenv("NO_COLOR"):
        return False
    target = stream if stream is not None else sys.stdout
    return bool(getattr(target, "isatty", lambda: False)())


def unified_diff_text(
    before: str,
    after: str,
    *,
    fromfile: str = "a/file.py",
    tofile: str = "b/file.py",
    n: int = 3,
) -> str:
    """Return a unified diff string (no trailing color codes)."""
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=fromfile,
        tofile=tofile,
        n=n,
    )
    return "".join(diff)


def colorize_diff(diff_text: str, *, color: bool | None = None) -> str:
    """Colorize unified diff lines for terminal display."""
    if color is None:
        color = _use_color()
    if not color or not diff_text:
        return diff_text

    out: list[str] = []
    for line in diff_text.splitlines(keepends=True):
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            out.append(f"{_Colors.CYAN}{line}{_Colors.RESET}")
        elif line.startswith("+"):
            out.append(f"{_Colors.GREEN}{line}{_Colors.RESET}")
        elif line.startswith("-"):
            out.append(f"{_Colors.RED}{line}{_Colors.RESET}")
        else:
            out.append(line)
    return "".join(out)


def format_file_diff(
    path: str,
    before: str,
    after: str,
    *,
    color: bool | None = None,
) -> str:
    """Build a colored unified diff for a single file path."""
    label = path.replace("\\", "/")
    raw = unified_diff_text(
        before,
        after,
        fromfile=f"a/{label}",
        tofile=f"b/{label}",
    )
    return colorize_diff(raw, color=color)


def print_diff(diff_text: str, *, stream: object | None = None) -> None:
    """Write a (possibly colored) diff to ``stream`` (default stdout)."""
    target = sys.stdout if stream is None else stream
    colored = colorize_diff(diff_text, color=_use_color(target))
    write = getattr(target, "write", None)
    if callable(write):
        write(colored)
        if colored and not colored.endswith("\n"):
            write("\n")

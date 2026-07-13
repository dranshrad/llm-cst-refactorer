# SPDX-License-Identifier: AGPL-3.0-or-later
"""Discover Python source files under a path with include/exclude globs."""

from __future__ import annotations

import fnmatch
from pathlib import Path


def _matches_any(rel: str, patterns: tuple[str, ...]) -> bool:
    name = Path(rel).name
    for pattern in patterns:
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
            return True
        if pattern.startswith("**/"):
            rest = pattern[3:]
            if fnmatch.fnmatch(rel, rest) or fnmatch.fnmatch(name, rest):
                return True
            # Match if any path suffix matches the rest pattern
            parts = rel.split("/")
            for i in range(len(parts)):
                suffix = "/".join(parts[i:])
                if fnmatch.fnmatch(suffix, rest):
                    return True
        simplified = pattern.replace("**/", "").replace("/**", "")
        if simplified != pattern and (
            fnmatch.fnmatch(rel, simplified) or fnmatch.fnmatch(rel, f"*/{simplified}")
        ):
            return True
    return False


def discover_python_files(
    root: Path,
    *,
    include: tuple[str, ...] = ("**/*.py",),
    exclude: tuple[str, ...] = (),
) -> list[Path]:
    """Return sorted .py files under ``root`` matching include and not exclude.

    ``.pyi`` stubs are never included.
    """
    root = root.resolve()
    if root.is_file():
        if root.suffix == ".py":
            return [root]
        return []

    results: list[Path] = []
    for path in root.rglob("*.py"):
        if not path.is_file():
            continue
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        if not _matches_any(rel, include):
            continue
        if _matches_any(rel, exclude):
            continue
        parts = set(Path(rel).parts)
        if parts & {".venv", "venv", "__pycache__", ".git", "site-packages", ".mypy_cache"}:
            continue
        results.append(path.resolve())

    return sorted(results)

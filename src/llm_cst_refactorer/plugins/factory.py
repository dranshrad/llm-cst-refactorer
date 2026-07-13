# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plugin registry / factory."""

from __future__ import annotations

from llm_cst_refactorer.plugins.base import RefactorPlugin
from llm_cst_refactorer.plugins.typing_docstring import TypingDocstringPlugin

_REGISTRY: dict[str, type] = {
    TypingDocstringPlugin.name: TypingDocstringPlugin,
}


def create_plugin(name: str = "typing-docstring") -> RefactorPlugin:
    """Instantiate a registered plugin by name."""
    key = name.strip().lower()
    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown plugin {name!r}. Known: {known}") from exc
    return cls()  # type: ignore[no-any-return]

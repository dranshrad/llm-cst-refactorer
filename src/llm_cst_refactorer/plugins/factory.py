# SPDX-License-Identifier: AGPL-3.0-or-later
"""Plugin registry / factory."""

from __future__ import annotations

from llm_cst_refactorer.plugins.base import RefactorPlugin
from llm_cst_refactorer.plugins.init_return_none import InitReturnNonePlugin
from llm_cst_refactorer.plugins.typing_docstring import TypingDocstringPlugin

_REGISTRY: dict[str, type] = {
    InitReturnNonePlugin.name: InitReturnNonePlugin,
    TypingDocstringPlugin.name: TypingDocstringPlugin,
}

DEFAULT_PLUGIN_LIST = "init-return-none,typing-docstring"


def create_plugin(name: str = "typing-docstring") -> RefactorPlugin:
    """Instantiate a registered plugin by name."""
    key = name.strip().lower()
    try:
        cls = _REGISTRY[key]
    except KeyError as exc:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Unknown plugin {name!r}. Known: {known}") from exc
    return cls()  # type: ignore[no-any-return]


def create_plugins(spec: str | None = None) -> list[RefactorPlugin]:
    """Instantiate a comma-separated plugin list (order preserved)."""
    raw = (spec or DEFAULT_PLUGIN_LIST).strip()
    if not raw:
        raw = DEFAULT_PLUGIN_LIST
    names = [part.strip() for part in raw.split(",") if part.strip()]
    if not names:
        raise ValueError("At least one plugin name is required.")
    return [create_plugin(name) for name in names]

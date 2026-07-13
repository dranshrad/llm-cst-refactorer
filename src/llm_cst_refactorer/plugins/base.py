# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stable plugin Protocol (api_version = \"1\")."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.providers.base import LLMProvider
from llm_cst_refactorer.semantic import SemanticFunction

PLUGIN_API_VERSION = "1"


@runtime_checkable
class RefactorPlugin(Protocol):
    """Feature plugin that proposes transformations for a SemanticFunction."""

    name: str
    api_version: str

    def select(self, fn: SemanticFunction) -> bool:
        """Return True if this plugin should handle ``fn``."""
        ...

    async def propose(
        self,
        fn: SemanticFunction,
        provider: LLMProvider,
        *,
        repair: str | None = None,
    ) -> Suggestion:
        """Return a structured suggestion for ``fn``."""
        ...

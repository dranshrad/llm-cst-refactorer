# SPDX-License-Identifier: AGPL-3.0-or-later
"""Default typing + Google docstring plugin."""

from __future__ import annotations

from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.plugins.base import PLUGIN_API_VERSION
from llm_cst_refactorer.providers.base import LLMProvider
from llm_cst_refactorer.semantic import SemanticFunction


class TypingDocstringPlugin:
    """Propose missing parameter/return annotations and Google-style docstrings."""

    name = "typing-docstring"
    api_version = PLUGIN_API_VERSION

    def select(self, fn: SemanticFunction) -> bool:
        return fn.needs.any

    async def propose(
        self,
        fn: SemanticFunction,
        provider: LLMProvider,
        *,
        repair: str | None = None,
    ) -> Suggestion:
        return await provider.suggest(fn, repair_errors=repair)

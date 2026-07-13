# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic plugin: annotate ``__init__`` return as ``None`` (no LLM)."""

from __future__ import annotations

from llm_cst_refactorer.models import FieldSuggestion, Suggestion
from llm_cst_refactorer.plugins.base import PLUGIN_API_VERSION
from llm_cst_refactorer.providers.base import LLMProvider
from llm_cst_refactorer.semantic import SemanticFunction


class InitReturnNonePlugin:
    """Apply the conventional ``-> None`` return annotation on ``__init__``."""

    name = "init-return-none"
    api_version = PLUGIN_API_VERSION

    def select(self, fn: SemanticFunction) -> bool:
        short = fn.qualified_name.rsplit(".", 1)[-1]
        return short == "__init__" and fn.return_annotation is None

    async def propose(
        self,
        fn: SemanticFunction,
        provider: LLMProvider,
        *,
        repair: str | None = None,
    ) -> Suggestion:
        _ = (fn, provider, repair)
        return Suggestion(
            return_type=FieldSuggestion(
                value="None",
                confidence=1.0,
                evidence=["__init__ convention"],
            )
        )

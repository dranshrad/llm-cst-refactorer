# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider protocol and shared helpers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.semantic import SemanticFunction


@runtime_checkable
class LLMProvider(Protocol):
    """Async interface for docstring / typing suggestion backends."""

    async def suggest(
        self,
        fn: SemanticFunction,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        """Return a structured suggestion for ``fn``."""
        ...

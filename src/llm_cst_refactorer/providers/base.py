# SPDX-License-Identifier: AGPL-3.0-or-later
"""Provider protocol and shared helpers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from llm_cst_refactorer.models import FunctionContext, Suggestion


@runtime_checkable
class LLMProvider(Protocol):
    """Async interface for docstring / typing suggestion backends."""

    async def suggest(
        self,
        ctx: FunctionContext,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        """Return a structured suggestion for ``ctx``."""
        ...

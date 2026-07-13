# SPDX-License-Identifier: AGPL-3.0-or-later
"""Anthropic Messages API provider."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from llm_cst_refactorer.models import FunctionContext, Suggestion
from llm_cst_refactorer.prompts import SYSTEM_PROMPT, build_user_prompt, parse_suggestion_json


class AnthropicProvider:
    """Generate suggestions via the Anthropic async client."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int = 2048,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def suggest(
        self,
        ctx: FunctionContext,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": build_user_prompt(ctx, repair_errors=repair_errors),
                }
            ],
        )
        chunks: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                chunks.append(text)
        raw = "".join(chunks)
        return parse_suggestion_json(raw)

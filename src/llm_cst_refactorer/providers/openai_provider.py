# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenAI and OpenAI-compatible chat completions provider."""

from __future__ import annotations

from typing import Any, cast

from openai import AsyncOpenAI

from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.prompts import SYSTEM_PROMPT, build_user_prompt, parse_suggestion_json
from llm_cst_refactorer.semantic import SemanticFunction


class OpenAIProvider:
    """Generate suggestions via OpenAI Chat Completions (also Ollama-compatible)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> None:
        if base_url:
            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._json_mode = json_mode

    async def suggest(
        self,
        fn: SemanticFunction,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(fn, repair_errors=repair_errors),
            },
        ]
        create = self._client.chat.completions.create
        if self._json_mode:
            response = await create(
                model=self._model,
                temperature=self._temperature,
                response_format={"type": "json_object"},
                messages=cast(Any, messages),
            )
        else:
            response = await create(
                model=self._model,
                temperature=self._temperature,
                messages=cast(Any, messages),
            )
        content = response.choices[0].message.content or ""
        return parse_suggestion_json(content)

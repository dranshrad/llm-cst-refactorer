# SPDX-License-Identifier: AGPL-3.0-or-later
"""Construct an LLM provider from resolved settings."""

from __future__ import annotations

from llm_cst_refactorer.config import Engine, Settings
from llm_cst_refactorer.providers.anthropic_provider import AnthropicProvider
from llm_cst_refactorer.providers.base import LLMProvider
from llm_cst_refactorer.providers.openai_provider import OpenAIProvider


def create_provider(settings: Settings) -> LLMProvider:
    """Instantiate the provider selected by ``settings.engine``."""
    if settings.engine is Engine.ANTHROPIC:
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for --engine anthropic. "
                "Set it in the environment or a .env file."
            )
        return AnthropicProvider(api_key=settings.anthropic_api_key, model=settings.model)

    if settings.engine is Engine.OPENAI:
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for --engine openai. "
                "Set it in the environment or a .env file."
            )
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.model,
            base_url=settings.base_url,
        )

    if settings.engine is Engine.COMPATIBLE:
        if not settings.base_url:
            raise ValueError(
                "--base-url or LLM_CST_BASE_URL is required for --engine compatible "
                "(e.g. http://localhost:11434/v1 for Ollama)."
            )
        api_key = settings.openai_api_key or "ollama"
        return OpenAIProvider(
            api_key=api_key,
            model=settings.model,
            base_url=settings.base_url,
            json_mode=False,
        )

    raise ValueError(f"Unsupported engine: {settings.engine}")

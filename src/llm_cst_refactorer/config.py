# SPDX-License-Identifier: AGPL-3.0-or-later
"""Runtime configuration merged from CLI flags and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from dotenv import load_dotenv

DocstringStyle = Literal["google"]


class Engine(str, Enum):
    """Supported LLM backend engines."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    COMPATIBLE = "compatible"


DEFAULT_MODELS: dict[Engine, str] = {
    Engine.ANTHROPIC: "claude-sonnet-4-20250514",
    Engine.OPENAI: "gpt-4.1-mini",
    Engine.COMPATIBLE: "llama3.2",
}


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved settings for a refactor run."""

    engine: Engine
    model: str
    base_url: str | None
    apply: bool
    concurrency: int
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    docstring_style: DocstringStyle
    types_only: bool
    docs_only: bool
    max_retries: int
    force: bool
    verbose: bool
    anthropic_api_key: str | None
    openai_api_key: str | None


def load_settings(
    *,
    engine: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    apply: bool = False,
    concurrency: int = 4,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    docstring_style: DocstringStyle = "google",
    types_only: bool = False,
    docs_only: bool = False,
    max_retries: int = 2,
    force: bool = False,
    verbose: bool = False,
) -> Settings:
    """Load dotenv and merge CLI overrides with environment defaults."""
    load_dotenv()

    engine_raw = (engine or os.getenv("LLM_CST_ENGINE") or Engine.ANTHROPIC.value).lower()
    try:
        resolved_engine = Engine(engine_raw)
    except ValueError as exc:
        valid = ", ".join(e.value for e in Engine)
        raise ValueError(f"Unknown engine {engine_raw!r}. Expected one of: {valid}") from exc

    resolved_model = model or os.getenv("LLM_CST_MODEL") or DEFAULT_MODELS[resolved_engine]
    resolved_base = base_url or os.getenv("LLM_CST_BASE_URL") or None

    default_exclude = [
        "**/.venv/**",
        "**/venv/**",
        "**/__pycache__/**",
        "**/.git/**",
        "**/site-packages/**",
        "**/.mypy_cache/**",
        "**/.ruff_cache/**",
        "**/node_modules/**",
    ]

    return Settings(
        engine=resolved_engine,
        model=resolved_model,
        base_url=resolved_base,
        apply=apply,
        concurrency=max(1, concurrency),
        include=tuple(include or ["**/*.py"]),
        exclude=tuple([*(exclude or []), *default_exclude]),
        docstring_style=docstring_style,
        types_only=types_only,
        docs_only=docs_only,
        max_retries=max(0, max_retries),
        force=force,
        verbose=verbose,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY") or None,
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
    )

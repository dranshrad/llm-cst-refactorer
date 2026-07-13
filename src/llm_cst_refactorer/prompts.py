# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prompt templates for structured type and docstring generation."""

from __future__ import annotations

import json

from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.semantic import PROMPT_VERSION, SemanticFunction

SYSTEM_PROMPT = (
    """\
You are a senior Python typing and documentation assistant.
Given a SemanticFunction payload (source + repository context), return ONLY JSON:

{
  "param_types": {
    "name": {"value": "str", "confidence": 0.0-1.0, "evidence": ["..."]}
  },
  "return_type": {"value": "int", "confidence": 0.9, "evidence": ["..."]} | null,
  "docstring": {
    "value": "Google-style body WITHOUT triple quotes",
    "confidence": 0.8,
    "evidence": ["..."]
  } | null
}

Rules:
1. Output valid JSON only. No markdown fences, no commentary.
2. Use precise built-in and typing annotations (list[str], dict[str, int], X | None, etc.).
3. Do not invent parameters that are not listed as missing.
4. Skip annotating self/cls.
5. Google docstring sections when useful: Args, Returns, Raises, Yields.
6. Keep the docstring accurate and concise; do not invent undocumented side effects.
7. Prefer names/types from repo_context.imported_names and convention_hints.
8. confidence must reflect certainty; cite short evidence strings.
9. Prompt schema version: """
    + PROMPT_VERSION
    + "\n"
)


def build_user_prompt(fn: SemanticFunction, *, repair_errors: str | None = None) -> str:
    """Build the user message for suggestion or repair."""
    payload = fn.prompt_payload()
    parts = [
        "Analyze this SemanticFunction and return JSON matching the schema.",
        json.dumps(payload, indent=2),
    ]
    if repair_errors:
        parts.append(
            "The previous suggestion failed verification with these errors. "
            "Return a corrected JSON suggestion:\n"
            f"{repair_errors}"
        )
    return "\n\n".join(parts)


def parse_suggestion_json(raw: str) -> Suggestion:
    """Parse and validate a model JSON payload into Suggestion."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.lower().startswith("json"):
            text = text[4:].lstrip()

    data = json.loads(text)
    return Suggestion.model_validate(data)

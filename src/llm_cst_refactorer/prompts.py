# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prompt templates for structured type and docstring generation."""

from __future__ import annotations

import json

from llm_cst_refactorer.models import FunctionContext, Suggestion

SYSTEM_PROMPT = """\
You are a senior Python typing and documentation assistant.
Given a function and optional module context, return ONLY a JSON object with:
- "param_types": object mapping parameter names to Python type annotation strings
- "return_type": a Python return annotation string, or null if not needed
- "docstring": a Google-style docstring body WITHOUT surrounding triple quotes, or null

Rules:
1. Output valid JSON only. No markdown fences, no commentary.
2. Use precise built-in and typing annotations (list[str], dict[str, int], X | None, etc.).
3. Do not invent parameters that are not listed as missing.
4. Skip annotating self/cls.
5. Google docstring sections when useful: Args, Returns, Raises, Yields.
6. Keep the docstring accurate and concise; do not invent undocumented side effects.
7. Prefer existing names from the module preamble when choosing types.
"""


def build_user_prompt(ctx: FunctionContext, *, repair_errors: str | None = None) -> str:
    """Build the user message for suggestion or repair."""
    payload = {
        "qualified_name": ctx.qualified_name,
        "file_path": ctx.file_path,
        "is_async": ctx.is_async,
        "is_method": ctx.is_method,
        "param_names": ctx.param_names,
        "missing_param_names": ctx.missing_param_names,
        "has_return_annotation": ctx.has_return_annotation,
        "has_docstring": ctx.has_docstring,
        "needs": ctx.needs.model_dump(),
        "module_preamble": ctx.module_preamble,
        "class_context": ctx.class_context,
        "function_source": ctx.function_source,
    }
    parts = [
        "Analyze this function and return JSON matching the schema.",
        json.dumps(payload, indent=2),
    ]
    if repair_errors:
        parts.append(
            "The previous suggestion failed mypy with these errors. "
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

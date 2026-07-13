# SPDX-License-Identifier: AGPL-3.0-or-later
"""Schema verification for annotations and docstrings in a Suggestion."""

from __future__ import annotations

import libcst as cst

from llm_cst_refactorer.models import StageError, Suggestion, VerificationResult
from llm_cst_refactorer.semantic import SemanticFunction


def verify_suggestion_schema(fn: SemanticFunction, suggestion: Suggestion) -> VerificationResult:
    """Validate annotation expressions parse and required fields look sane."""
    stages: list[StageError] = []

    for name, field in suggestion.param_types.items():
        if name not in fn.missing_param_names and name not in fn.param_names:
            stages.append(StageError(stage="schema", message=f"unexpected parameter {name!r}"))
            continue
        if not _annotation_parses(field.value):
            stages.append(
                StageError(
                    stage="schema",
                    message=f"param {name!r} annotation does not parse: {field.value!r}",
                )
            )

    if suggestion.return_type is not None and not _annotation_parses(suggestion.return_type.value):
        stages.append(
            StageError(
                stage="schema",
                message=f"return annotation does not parse: {suggestion.return_type.value!r}",
            )
        )

    if fn.needs.needs_docstring and suggestion.docstring is not None:
        body = suggestion.docstring.value.strip()
        if not body:
            stages.append(StageError(stage="schema", message="docstring is empty"))

    if stages:
        return VerificationResult(
            ok=False,
            errors="; ".join(s.message for s in stages),
            stages=stages,
        )
    return VerificationResult(ok=True)


def _annotation_parses(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    try:
        module = cst.parse_module(f"def _f() -> {cleaned}:\n    pass\n")
        func = module.body[0]
        return isinstance(func, cst.FunctionDef) and func.returns is not None
    except cst.ParserSyntaxError:
        return False

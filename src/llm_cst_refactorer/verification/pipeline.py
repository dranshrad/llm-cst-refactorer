# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compose syntax → schema → mypy verification stages."""

from __future__ import annotations

from llm_cst_refactorer.models import StageError, Suggestion, VerificationResult
from llm_cst_refactorer.semantic import SemanticFunction
from llm_cst_refactorer.verification.mypy_verifier import verify_mypy
from llm_cst_refactorer.verification.schema_verifier import verify_suggestion_schema
from llm_cst_refactorer.verification.syntax_verifier import verify_syntax


class VerifierPipeline:
    """Multi-stage verification with aggregated stage-tagged errors."""

    def run(
        self,
        candidate_source: str,
        *,
        fn: SemanticFunction | None = None,
        suggestion: Suggestion | None = None,
        skip_mypy: bool = False,
    ) -> VerificationResult:
        stages: list[StageError] = []

        syntax = verify_syntax(candidate_source)
        if not syntax.ok:
            return syntax

        if fn is not None and suggestion is not None:
            schema = verify_suggestion_schema(fn, suggestion)
            if not schema.ok:
                return schema

        if skip_mypy:
            return VerificationResult(ok=True, stages=stages)

        mypy = verify_mypy(candidate_source)
        return mypy


def verify_candidate(
    candidate_source: str,
    *,
    fn: SemanticFunction | None = None,
    suggestion: Suggestion | None = None,
    force: bool = False,
) -> VerificationResult:
    """Convenience entrypoint used by the client coordinator."""
    return VerifierPipeline().run(
        candidate_source,
        fn=fn,
        suggestion=suggestion,
        skip_mypy=force,
    )

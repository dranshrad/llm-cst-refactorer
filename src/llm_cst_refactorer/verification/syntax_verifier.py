# SPDX-License-Identifier: AGPL-3.0-or-later
"""Syntax verification via LibCST parse."""

from __future__ import annotations

import libcst as cst

from llm_cst_refactorer.models import StageError, VerificationResult


def verify_syntax(source: str) -> VerificationResult:
    """Ensure ``source`` parses as a Python module with LibCST."""
    try:
        cst.parse_module(source)
    except cst.ParserSyntaxError as exc:
        return VerificationResult(
            ok=False,
            errors=str(exc),
            stages=[StageError(stage="syntax", message=str(exc))],
        )
    return VerificationResult(ok=True)

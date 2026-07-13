# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared Pydantic models for function context and LLM suggestions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FunctionNeeds(BaseModel):
    """Flags describing what is missing on a function."""

    needs_params: bool = False
    needs_return: bool = False
    needs_docstring: bool = False

    @property
    def any(self) -> bool:
        return self.needs_params or self.needs_return or self.needs_docstring


class FunctionContext(BaseModel):
    """Context payload sent to an LLM for a single function."""

    qualified_name: str
    function_source: str
    module_preamble: str = ""
    class_context: str | None = None
    param_names: list[str] = Field(default_factory=list)
    missing_param_names: list[str] = Field(default_factory=list)
    has_return_annotation: bool = False
    has_docstring: bool = False
    is_async: bool = False
    is_method: bool = False
    needs: FunctionNeeds = Field(default_factory=FunctionNeeds)
    file_path: str = ""
    lineno: int = 0


class Suggestion(BaseModel):
    """Structured LLM response for types and docstring."""

    param_types: dict[str, str] = Field(default_factory=dict)
    return_type: str | None = None
    docstring: str | None = None


class VerificationResult(BaseModel):
    """Outcome of a local mypy verification pass."""

    ok: bool
    errors: str = ""

# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared Pydantic models for suggestions and verification."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class FunctionNeeds(BaseModel):
    """Flags describing what is missing on a function."""

    needs_params: bool = False
    needs_return: bool = False
    needs_docstring: bool = False

    @property
    def any(self) -> bool:
        return self.needs_params or self.needs_return or self.needs_docstring


class FieldSuggestion(BaseModel):
    """A single suggested value with confidence and evidence."""

    value: str
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: str | dict[str, Any] | FieldSuggestion) -> FieldSuggestion:
        """Coerce legacy plain strings or dicts into FieldSuggestion."""
        if isinstance(raw, FieldSuggestion):
            return raw
        if isinstance(raw, str):
            return cls(value=raw, confidence=0.7, evidence=[])
        if isinstance(raw, dict):
            return cls.model_validate(raw)
        raise TypeError(f"Cannot coerce {type(raw)!r} to FieldSuggestion")


class Suggestion(BaseModel):
    """Structured LLM response for types and docstring."""

    param_types: dict[str, FieldSuggestion] = Field(default_factory=dict)
    return_type: FieldSuggestion | None = None
    docstring: FieldSuggestion | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        params = out.get("param_types") or {}
        if isinstance(params, dict):
            out["param_types"] = {
                str(k): FieldSuggestion.from_raw(v).model_dump() for k, v in params.items()
            }
        if "return_type" in out and out["return_type"] is not None:
            out["return_type"] = FieldSuggestion.from_raw(out["return_type"]).model_dump()
        if "docstring" in out and out["docstring"] is not None:
            out["docstring"] = FieldSuggestion.from_raw(out["docstring"]).model_dump()
        return out

    def param_type_map(self) -> dict[str, str]:
        """Plain name → annotation string map for CST application."""
        return {name: field.value for name, field in self.param_types.items()}

    def return_type_value(self) -> str | None:
        return self.return_type.value if self.return_type else None

    def docstring_value(self) -> str | None:
        return self.docstring.value if self.docstring else None

    def filter_by_confidence(self, minimum: float) -> Suggestion:
        """Drop fields below ``minimum`` confidence."""
        params = {
            name: field for name, field in self.param_types.items() if field.confidence >= minimum
        }
        ret = (
            self.return_type
            if self.return_type and self.return_type.confidence >= minimum
            else None
        )
        doc = self.docstring if self.docstring and self.docstring.confidence >= minimum else None
        return Suggestion(param_types=params, return_type=ret, docstring=doc)

    def is_empty(self) -> bool:
        return not self.param_types and self.return_type is None and self.docstring is None


class StageError(BaseModel):
    """A verification failure tagged by pipeline stage."""

    stage: str
    message: str


class VerificationResult(BaseModel):
    """Outcome of a verification pass (single stage or pipeline)."""

    ok: bool
    errors: str = ""
    stages: list[StageError] = Field(default_factory=list)

    @field_validator("stages", mode="before")
    @classmethod
    def _default_stages(cls, value: Any) -> Any:
        return value or []

    def format_for_repair(self) -> str:
        if self.stages:
            parts = [f"[{s.stage}] {s.message}" for s in self.stages]
            return "\n".join(parts)
        return self.errors

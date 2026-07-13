# SPDX-License-Identifier: AGPL-3.0-or-later
"""SemanticFunction intermediate representation for plugins and prompts."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from llm_cst_refactorer.models import FunctionNeeds

PROMPT_VERSION = "v2"


class ParamInfo(BaseModel):
    """Parameter metadata independent of CST rendering."""

    name: str
    annotation: str | None = None
    has_default: bool = False
    is_self_or_cls: bool = False


class RepoContextSlice(BaseModel):
    """Truncated repository context attached to a function for prompting."""

    module_preamble: str = ""
    class_context: str | None = None
    neighboring_symbols: list[str] = Field(default_factory=list)
    imported_names: list[str] = Field(default_factory=list)
    convention_hints: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)


class SemanticFunction(BaseModel):
    """Rendering-independent semantic representation of a function."""

    qualified_name: str
    file_path: str = ""
    lineno: int = 0
    is_async: bool = False
    is_method: bool = False
    source: str
    params: list[ParamInfo] = Field(default_factory=list)
    return_annotation: str | None = None
    docstring: str | None = None
    needs: FunctionNeeds = Field(default_factory=FunctionNeeds)
    repo_context: RepoContextSlice = Field(default_factory=RepoContextSlice)
    fingerprint: str = ""

    @property
    def param_names(self) -> list[str]:
        return [p.name for p in self.params]

    @property
    def missing_param_names(self) -> list[str]:
        return [p.name for p in self.params if not p.is_self_or_cls and p.annotation is None]

    @property
    def has_return_annotation(self) -> bool:
        return self.return_annotation is not None

    @property
    def has_docstring(self) -> bool:
        return bool(self.docstring)

    def compute_fingerprint(self) -> str:
        """Stable hash of identity + source + needs for cache keys."""
        payload: dict[str, Any] = {
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "source": self.source,
            "needs": self.needs.model_dump(),
            "prompt_version": PROMPT_VERSION,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def with_fingerprint(self) -> SemanticFunction:
        return self.model_copy(update={"fingerprint": self.compute_fingerprint()})

    def prompt_payload(self) -> dict[str, Any]:
        """JSON-serializable payload for LLM prompts."""
        return {
            "qualified_name": self.qualified_name,
            "file_path": self.file_path,
            "lineno": self.lineno,
            "is_async": self.is_async,
            "is_method": self.is_method,
            "param_names": self.param_names,
            "missing_param_names": self.missing_param_names,
            "has_return_annotation": self.has_return_annotation,
            "has_docstring": self.has_docstring,
            "needs": self.needs.model_dump(),
            "function_source": self.source,
            "repo_context": self.repo_context.model_dump(),
        }

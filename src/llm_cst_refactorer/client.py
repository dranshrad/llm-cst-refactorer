# SPDX-License-Identifier: AGPL-3.0-or-later
"""Async coordinator: collect → LLM suggest → mypy verify → apply."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from llm_cst_refactorer.collector import collect_functions
from llm_cst_refactorer.config import Settings
from llm_cst_refactorer.diff_util import format_file_diff
from llm_cst_refactorer.models import FunctionContext, Suggestion
from llm_cst_refactorer.prompts import parse_suggestion_json
from llm_cst_refactorer.providers.base import LLMProvider
from llm_cst_refactorer.transformer import apply_suggestion, apply_suggestions
from llm_cst_refactorer.type_verifier import verify_source

logger = logging.getLogger(__name__)


@dataclass
class FileResult:
    """Outcome of processing a single Python file."""

    path: Path
    before: str
    after: str
    changed: bool
    functions_updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def diff(self) -> str:
        if not self.changed:
            return ""
        return format_file_diff(str(self.path), self.before, self.after, color=False)


@dataclass
class RefactorReport:
    """Aggregate report across all processed files."""

    results: list[FileResult] = field(default_factory=list)

    @property
    def files_changed(self) -> int:
        return sum(1 for r in self.results if r.changed)

    @property
    def functions_updated(self) -> int:
        return sum(len(r.functions_updated) for r in self.results)


def _filter_suggestion(ctx: FunctionContext, suggestion: Suggestion) -> Suggestion:
    """Keep only fields that were requested and relevant."""
    param_types = {
        name: ann for name, ann in suggestion.param_types.items() if name in ctx.missing_param_names
    }
    return_type = suggestion.return_type if ctx.needs.needs_return else None
    docstring = suggestion.docstring if ctx.needs.needs_docstring else None
    return Suggestion(param_types=param_types, return_type=return_type, docstring=docstring)


async def _suggest_with_retries(
    provider: LLMProvider,
    ctx: FunctionContext,
    *,
    current_source: str,
    max_retries: int,
    force: bool,
) -> Suggestion | None:
    """Ask the provider, verify with mypy, and optionally repair."""
    repair_errors: str | None = None
    attempts = max_retries + 1
    last_error = ""

    for attempt in range(attempts):
        try:
            raw_suggestion = await provider.suggest(ctx, repair_errors=repair_errors)
        except Exception as exc:
            last_error = f"provider error: {exc}"
            logger.warning("%s: %s", ctx.qualified_name, last_error)
            # One parse/repair style retry is handled by attempts loop when JSON fails
            if attempt + 1 >= attempts:
                return None
            repair_errors = last_error
            continue

        suggestion = _filter_suggestion(ctx, raw_suggestion)
        if (
            not suggestion.param_types
            and suggestion.return_type is None
            and suggestion.docstring is None
        ):
            last_error = "empty suggestion after filtering"
            logger.warning("%s: %s", ctx.qualified_name, last_error)
            return None

        candidate = apply_suggestion(current_source, ctx.qualified_name, suggestion)
        if force:
            return suggestion

        verification = verify_source(candidate)
        if verification.ok:
            return suggestion

        last_error = verification.errors
        repair_errors = verification.errors
        logger.info(
            "mypy rejected suggestion for %s (attempt %s/%s)",
            ctx.qualified_name,
            attempt + 1,
            attempts,
        )

    logger.warning("Giving up on %s: %s", ctx.qualified_name, last_error)
    return None


async def process_file(
    path: Path,
    provider: LLMProvider,
    settings: Settings,
) -> FileResult:
    """Refactor a single file and return before/after plus metadata."""
    before = path.read_text(encoding="utf-8")
    collected = collect_functions(
        before,
        file_path=str(path),
        types_only=settings.types_only,
        docs_only=settings.docs_only,
    )
    if not collected:
        return FileResult(path=path, before=before, after=before, changed=False)

    semaphore = asyncio.Semaphore(settings.concurrency)
    updates: dict[str, Suggestion] = {}
    skipped: list[str] = []
    errors: list[str] = []

    async def handle(ctx: FunctionContext) -> None:
        async with semaphore:
            suggestion = await _suggest_with_retries(
                provider,
                ctx,
                current_source=before,
                max_retries=settings.max_retries,
                force=settings.force,
            )
            if suggestion is None:
                skipped.append(ctx.qualified_name)
                errors.append(f"{ctx.qualified_name}: failed verification or provider")
            else:
                updates[ctx.qualified_name] = suggestion

    await asyncio.gather(*(handle(item.context) for item in collected))

    if not updates:
        return FileResult(
            path=path,
            before=before,
            after=before,
            changed=False,
            skipped=skipped,
            errors=errors,
        )

    after = apply_suggestions(before, updates)
    # Final whole-file verification unless forced
    if not settings.force:
        final = verify_source(after)
        if not final.ok:
            return FileResult(
                path=path,
                before=before,
                after=before,
                changed=False,
                skipped=[*skipped, *updates.keys()],
                errors=[*errors, f"final mypy failed: {final.errors}"],
            )

    return FileResult(
        path=path,
        before=before,
        after=after,
        changed=after != before,
        functions_updated=sorted(updates.keys()),
        skipped=skipped,
        errors=errors,
    )


async def run_refactor(
    paths: list[Path],
    provider: LLMProvider,
    settings: Settings,
) -> RefactorReport:
    """Process many files sequentially (LLM calls inside each file are concurrent)."""
    report = RefactorReport()
    for path in paths:
        if settings.verbose:
            logger.info("Processing %s", path)
        result = await process_file(path, provider, settings)
        report.results.append(result)
    return report


def suggest_from_raw_json(raw: str) -> Suggestion:
    """Public helper used by tests to parse model JSON."""
    return parse_suggestion_json(raw)

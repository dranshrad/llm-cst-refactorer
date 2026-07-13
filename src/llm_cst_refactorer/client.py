# SPDX-License-Identifier: AGPL-3.0-or-later
"""Async coordinator: index → collect → plugins/LLM → verify → apply."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from llm_cst_refactorer.cache import SuggestionCache
from llm_cst_refactorer.collector import collect_functions
from llm_cst_refactorer.config import Settings
from llm_cst_refactorer.diff_util import format_file_diff
from llm_cst_refactorer.metrics import RunMetrics
from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.plugins.base import RefactorPlugin
from llm_cst_refactorer.plugins.factory import create_plugins
from llm_cst_refactorer.prompts import build_user_prompt, parse_suggestion_json
from llm_cst_refactorer.providers.base import LLMProvider
from llm_cst_refactorer.repo_index import RepoIndex
from llm_cst_refactorer.semantic import SemanticFunction
from llm_cst_refactorer.transformer import apply_suggestion, apply_suggestions
from llm_cst_refactorer.verification.pipeline import verify_candidate

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
    metrics: RunMetrics = field(default_factory=RunMetrics)

    @property
    def files_changed(self) -> int:
        return sum(1 for r in self.results if r.changed)

    @property
    def functions_updated(self) -> int:
        return sum(len(r.functions_updated) for r in self.results)


def merge_suggestions(base: Suggestion, extra: Suggestion) -> Suggestion:
    """Merge two suggestions; earlier non-None return/docstring wins."""
    return Suggestion(
        param_types={**base.param_types, **extra.param_types},
        return_type=base.return_type if base.return_type is not None else extra.return_type,
        docstring=base.docstring if base.docstring is not None else extra.docstring,
    )


def _filter_suggestion(fn: SemanticFunction, suggestion: Suggestion) -> Suggestion:
    """Keep only fields that were requested and relevant."""
    param_types = {
        name: field
        for name, field in suggestion.param_types.items()
        if name in fn.missing_param_names
    }
    return_type = suggestion.return_type if fn.needs.needs_return else None
    docstring = suggestion.docstring if fn.needs.needs_docstring else None
    return Suggestion(param_types=param_types, return_type=return_type, docstring=docstring)


async def _suggest_with_retries(
    plugin: RefactorPlugin,
    provider: LLMProvider,
    fn: SemanticFunction,
    *,
    current_source: str,
    settings: Settings,
    cache: SuggestionCache | None,
    metrics: RunMetrics,
) -> Suggestion | None:
    """Ask the plugin/provider, verify with pipeline, and optionally repair."""
    engine = settings.engine.value
    model = settings.model
    plugin_name = plugin.name

    if cache is not None and settings.use_cache and not settings.refresh_cache:
        cached = cache.get(fn, engine=engine, model=model, plugin=plugin_name)
        if cached is not None:
            metrics.cache_hits += 1
            filtered = _filter_suggestion(fn, cached).filter_by_confidence(settings.min_confidence)
            if filtered.is_empty():
                return None
            candidate = apply_suggestion(current_source, fn.qualified_name, filtered)
            verification = verify_candidate(
                candidate, fn=fn, suggestion=filtered, force=settings.force
            )
            if verification.ok or settings.force:
                metrics.verify_pass += 1
                return filtered
            metrics.verify_fail += 1
        else:
            metrics.cache_misses += 1
    elif cache is not None:
        metrics.cache_misses += 1

    repair_errors: str | None = None
    attempts = settings.max_retries + 1
    last_error = ""

    for attempt in range(attempts):
        try:
            t0 = time.perf_counter()
            prompt_chars = len(build_user_prompt(fn, repair_errors=repair_errors))
            raw_suggestion = await plugin.propose(fn, provider, repair=repair_errors)
            metrics.llm_calls += 1
            if attempt > 0:
                metrics.llm_retries += 1
            metrics.estimated_prompt_chars += prompt_chars
            metrics.estimated_completion_chars += len(raw_suggestion.model_dump_json())
            metrics.add_stage("llm", time.perf_counter() - t0)
        except Exception as exc:
            last_error = f"provider error: {exc}"
            logger.warning("%s: %s", fn.qualified_name, last_error)
            if attempt + 1 >= attempts:
                return None
            repair_errors = last_error
            continue

        suggestion = _filter_suggestion(fn, raw_suggestion).filter_by_confidence(
            settings.min_confidence
        )
        if suggestion.is_empty():
            last_error = "empty suggestion after filtering / confidence gate"
            logger.warning("%s: %s", fn.qualified_name, last_error)
            return None

        candidate = apply_suggestion(current_source, fn.qualified_name, suggestion)
        if settings.force:
            if cache is not None:
                cache.put(fn, suggestion, engine=engine, model=model, plugin=plugin_name)
            metrics.verify_pass += 1
            return suggestion

        t1 = time.perf_counter()
        verification = verify_candidate(candidate, fn=fn, suggestion=suggestion, force=False)
        metrics.add_stage("verify", time.perf_counter() - t1)
        if verification.ok:
            metrics.verify_pass += 1
            if cache is not None:
                cache.put(fn, suggestion, engine=engine, model=model, plugin=plugin_name)
            return suggestion

        metrics.verify_fail += 1
        last_error = verification.format_for_repair()
        repair_errors = last_error
        logger.info(
            "verification rejected suggestion for %s (attempt %s/%s)",
            fn.qualified_name,
            attempt + 1,
            attempts,
        )

    logger.warning("Giving up on %s: %s", fn.qualified_name, last_error)
    return None


async def process_file(
    path: Path,
    provider: LLMProvider,
    settings: Settings,
    *,
    repo_index: RepoIndex | None = None,
    plugins: list[RefactorPlugin] | None = None,
    plugin: RefactorPlugin | None = None,
    cache: SuggestionCache | None = None,
    metrics: RunMetrics | None = None,
) -> FileResult:
    """Refactor a single file and return before/after plus metadata."""
    metrics = metrics or RunMetrics()
    if plugins is None:
        plugins = [plugin] if plugin is not None else create_plugins(settings.plugin)
    before = path.read_text(encoding="utf-8")
    collected = collect_functions(
        before,
        file_path=str(path.resolve()),
        types_only=settings.types_only,
        docs_only=settings.docs_only,
    )
    if not collected:
        return FileResult(path=path, before=before, after=before, changed=False)

    functions: list[SemanticFunction] = []
    for item in collected:
        fn = item.semantic
        if repo_index is not None:
            fn = repo_index.attach(fn)
        if any(p.select(fn) for p in plugins):
            functions.append(fn)

    if not functions:
        return FileResult(path=path, before=before, after=before, changed=False)

    semaphore = asyncio.Semaphore(settings.concurrency)
    updates: dict[str, Suggestion] = {}
    skipped: list[str] = []
    errors: list[str] = []

    async def handle(fn: SemanticFunction) -> None:
        async with semaphore:
            merged = Suggestion()
            got_any = False
            for plug in plugins:
                if not plug.select(fn):
                    continue
                suggestion = await _suggest_with_retries(
                    plug,
                    provider,
                    fn,
                    current_source=before,
                    settings=settings,
                    cache=cache,
                    metrics=metrics,
                )
                if suggestion is not None:
                    merged = merge_suggestions(merged, suggestion)
                    got_any = True
            if not got_any or merged.is_empty():
                skipped.append(fn.qualified_name)
                metrics.functions_skipped += 1
                errors.append(f"{fn.qualified_name}: failed verification or provider")
            else:
                # Re-verify merged candidate once
                candidate = apply_suggestion(before, fn.qualified_name, merged)
                if (
                    settings.force
                    or verify_candidate(candidate, fn=fn, suggestion=merged, force=False).ok
                ):
                    updates[fn.qualified_name] = merged
                else:
                    skipped.append(fn.qualified_name)
                    metrics.functions_skipped += 1
                    errors.append(f"{fn.qualified_name}: merged suggestion failed verification")

    await asyncio.gather(*(handle(fn) for fn in functions))

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
    if not settings.force:
        final = verify_candidate(after, force=False)
        if not final.ok:
            return FileResult(
                path=path,
                before=before,
                after=before,
                changed=False,
                skipped=[*skipped, *updates.keys()],
                errors=[*errors, f"final verification failed: {final.errors}"],
            )

    metrics.functions_updated += len(updates)
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
    """Process many files with a shared RepoIndex, plugins, cache, and metrics."""
    report = RefactorReport()
    metrics = report.metrics
    plugins = create_plugins(settings.plugin)

    t0 = time.perf_counter()
    repo_index = RepoIndex(paths)
    metrics.add_stage("index", time.perf_counter() - t0)

    cache: SuggestionCache | None = None
    if settings.use_cache or settings.refresh_cache:
        cache = SuggestionCache(settings.cache_dir)
        if settings.refresh_cache:
            cache.clear()

    for path in paths:
        if settings.verbose:
            logger.info("Processing %s", path)
        result = await process_file(
            path,
            provider,
            settings,
            repo_index=repo_index,
            plugins=plugins,
            cache=cache,
            metrics=metrics,
        )
        report.results.append(result)
        if result.changed:
            metrics.files_changed += 1

    metrics.finish()
    if settings.report_path is not None:
        metrics.write_json(settings.report_path)
    return report


def suggest_from_raw_json(raw: str) -> Suggestion:
    """Public helper used by tests to parse model JSON."""
    return parse_suggestion_json(raw)

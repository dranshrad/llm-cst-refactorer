# SPDX-License-Identifier: AGPL-3.0-or-later
"""Typer CLI for the LLM semantic refactoring engine."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler

from llm_cst_refactorer import __version__
from llm_cst_refactorer.client import run_refactor
from llm_cst_refactorer.config import load_settings
from llm_cst_refactorer.diff_util import format_file_diff
from llm_cst_refactorer.providers.factory import create_provider
from llm_cst_refactorer.scanner import discover_python_files

console = Console(stderr=True)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


def main(
    path: Annotated[
        Path | None,
        typer.Argument(help="Python file or directory to analyze."),
    ] = None,
    engine: Annotated[
        str | None,
        typer.Option(
            "--engine",
            "-e",
            help="LLM backend: anthropic | openai | compatible.",
            envvar="LLM_CST_ENGINE",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="Model id override.",
            envvar="LLM_CST_MODEL",
        ),
    ] = None,
    base_url: Annotated[
        str | None,
        typer.Option(
            "--base-url",
            help="OpenAI-compatible base URL (required for --engine compatible).",
            envvar="LLM_CST_BASE_URL",
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Write changes to disk. Default is dry-run (preview diffs only).",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Preview diffs without writing (default behavior; explicit flag).",
        ),
    ] = False,
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", "-c", help="Max concurrent LLM calls."),
    ] = 4,
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include",
            help="Glob(s) of files to include (relative to PATH). Default: **/*.py",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Glob(s) of files to exclude."),
    ] = None,
    docstring_style: Annotated[
        str,
        typer.Option(
            "--docstring-style",
            help="Docstring style (v1 supports google only).",
        ),
    ] = "google",
    types_only: Annotated[
        bool,
        typer.Option("--types-only", help="Only add type annotations."),
    ] = False,
    docs_only: Annotated[
        bool,
        typer.Option("--docs-only", help="Only add docstrings."),
    ] = False,
    max_retries: Annotated[
        int,
        typer.Option(
            "--max-retries",
            help="Extra LLM repair attempts after verification failures.",
        ),
    ] = 2,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip mypy verification gate (discouraged)."),
    ] = False,
    min_confidence: Annotated[
        float,
        typer.Option(
            "--min-confidence",
            help="Drop suggestion fields below this confidence (0-1).",
        ),
    ] = 0.5,
    plugin: Annotated[
        str,
        typer.Option("--plugin", help="Refactor plugin name (default: typing-docstring)."),
    ] = "typing-docstring",
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Disable filesystem suggestion cache."),
    ] = False,
    refresh_cache: Annotated[
        bool,
        typer.Option("--refresh-cache", help="Clear cache then continue with caching enabled."),
    ] = False,
    report: Annotated[
        Path | None,
        typer.Option("--report", help="Write machine-readable metrics JSON to PATH."),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Verbose logging."),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show version and exit."),
    ] = False,
) -> None:
    """Refactor missing types/docstrings under PATH (dry-run by default)."""
    if version:
        typer.echo(__version__)
        raise typer.Exit(0)

    if path is None:
        console.print("[red]Missing argument PATH. Pass a file or directory.[/red]")
        raise typer.Exit(2)

    if not path.exists():
        console.print(f"[red]Path not found: {path}[/red]")
        raise typer.Exit(2)

    if types_only and docs_only:
        console.print("[red]Choose at most one of --types-only / --docs-only.[/red]")
        raise typer.Exit(2)

    if docstring_style != "google":
        console.print("[red]Only --docstring-style google is supported in v1.[/red]")
        raise typer.Exit(2)

    do_apply = bool(apply) and not dry_run

    _setup_logging(verbose)
    try:
        settings = load_settings(
            engine=engine,
            model=model,
            base_url=base_url,
            apply=do_apply,
            concurrency=concurrency,
            include=include,
            exclude=exclude,
            docstring_style="google",
            types_only=types_only,
            docs_only=docs_only,
            max_retries=max_retries,
            force=force,
            verbose=verbose,
            min_confidence=min_confidence,
            plugin=plugin,
            use_cache=not no_cache,
            refresh_cache=refresh_cache,
            report_path=report,
        )
        provider = create_provider(settings)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from exc

    files = discover_python_files(
        path,
        include=settings.include,
        exclude=settings.exclude,
    )
    if not files:
        console.print("[yellow]No Python files matched.[/yellow]")
        raise typer.Exit(0)

    console.print(
        f"Engine={settings.engine.value} model={settings.model} plugin={settings.plugin} "
        f"files={len(files)} mode={'apply' if settings.apply else 'dry-run'}"
    )

    refactor_report = asyncio.run(run_refactor(files, provider, settings))

    for result in refactor_report.results:
        if result.changed:
            diff = format_file_diff(str(result.path), result.before, result.after)
            typer.echo(diff)
            if settings.apply:
                result.path.write_text(result.after, encoding="utf-8")
                console.print(f"[green]Wrote[/green] {result.path}")
        elif result.errors and verbose:
            for err in result.errors:
                console.print(f"[yellow]{result.path}: {err}[/yellow]")

    mode = "Applied" if settings.apply else "Dry-run"
    console.print(
        f"{mode}: {refactor_report.files_changed} file(s) changed, "
        f"{refactor_report.functions_updated} function(s) updated."
    )
    console.print(f"[dim]{refactor_report.metrics.rich_summary()}[/dim]")
    if settings.report_path is not None:
        console.print(f"Metrics report written to {settings.report_path}")


def app() -> None:
    """Console-script entrypoint (Poetry: ``llm-cst-refactor``)."""
    typer.run(main)


cli = typer.Typer(add_completion=False)
cli.command()(main)

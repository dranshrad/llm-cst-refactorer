# SPDX-License-Identifier: AGPL-3.0-or-later
"""CLI and end-to-end dry-run tests with a mock provider."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cst_refactorer.cli import cli
from llm_cst_refactorer.client import process_file
from llm_cst_refactorer.config import load_settings
from llm_cst_refactorer.models import FunctionContext, Suggestion

runner = CliRunner()


class FakeProvider:
    async def suggest(
        self,
        ctx: FunctionContext,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        params = {name: "int" for name in ctx.missing_param_names}
        # Prefer str for names that look like strings
        for name in list(params):
            if name in {"name", "color", "path", "url"}:
                params[name] = "str"
        return_type = "str" if ctx.needs.needs_return else None
        if ctx.qualified_name.endswith("bump") or ctx.qualified_name == "add":
            return_type = "int"
        docstring = None
        if ctx.needs.needs_docstring:
            docstring = f"Auto docstring for {ctx.qualified_name}."
        return Suggestion(param_types=params, return_type=return_type, docstring=docstring)


@pytest.mark.asyncio
async def test_process_file_dry_logic(tmp_path: Path) -> None:
    target = tmp_path / "mod.py"
    target.write_text(
        """def add(a, b):
    return a + b
""",
        encoding="utf-8",
    )
    settings = load_settings(apply=False, force=False, max_retries=0)
    result = await process_file(target, FakeProvider(), settings)
    assert result.changed
    assert "def add(a: int, b: int) -> int:" in result.after
    assert target.read_text(encoding="utf-8") == result.before  # not written by process_file


def test_cli_help() -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "dry-run" in result.stdout.lower() or "dry-run" in result.output.lower()


def test_cli_version() -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_cli_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    target = tmp_path / "mod.py"
    target.write_text("def f(x):\n    return x\n", encoding="utf-8")
    result = runner.invoke(cli, [str(target), "--engine", "anthropic"])
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in result.output

# SPDX-License-Identifier: AGPL-3.0-or-later
"""CLI and end-to-end dry-run tests with a mock provider."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from llm_cst_refactorer.cli import cli
from llm_cst_refactorer.client import process_file
from llm_cst_refactorer.config import load_settings
from llm_cst_refactorer.models import FieldSuggestion, Suggestion
from llm_cst_refactorer.semantic import SemanticFunction

runner = CliRunner()


class FakeProvider:
    async def suggest(
        self,
        fn: SemanticFunction,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        params = {
            name: FieldSuggestion(value="int", confidence=0.9, evidence=["fake"])
            for name in fn.missing_param_names
        }
        for name in list(params):
            if name in {"name", "color", "path", "url"}:
                params[name] = FieldSuggestion(value="str", confidence=0.9, evidence=["name"])
        return_type = None
        if fn.needs.needs_return:
            value = "str"
            if fn.qualified_name.endswith("bump") or fn.qualified_name == "add":
                value = "int"
            return_type = FieldSuggestion(value=value, confidence=0.9, evidence=["body"])
        docstring = None
        if fn.needs.needs_docstring:
            docstring = FieldSuggestion(
                value=f"Auto docstring for {fn.qualified_name}.",
                confidence=0.8,
                evidence=["template"],
            )
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
    settings = load_settings(apply=False, force=False, max_retries=0, use_cache=False)
    result = await process_file(target, FakeProvider(), settings)
    assert result.changed
    assert "def add(a: int, b: int) -> int:" in result.after
    assert target.read_text(encoding="utf-8") == result.before


def test_cli_help() -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "dry-run" in result.stdout.lower() or "dry-run" in result.output.lower()


def test_cli_version() -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.stdout


def test_cli_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    target = tmp_path / "mod.py"
    target.write_text("def f(x):\n    return x\n", encoding="utf-8")
    result = runner.invoke(cli, [str(target), "--engine", "anthropic", "--no-cache"])
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in result.output

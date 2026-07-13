# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for SemanticFunction, RepoIndex, cache, metrics, and verifier pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from llm_cst_refactorer.cache import SuggestionCache
from llm_cst_refactorer.collector import collect_functions
from llm_cst_refactorer.metrics import RunMetrics
from llm_cst_refactorer.models import FieldSuggestion, Suggestion
from llm_cst_refactorer.plugins.factory import create_plugin
from llm_cst_refactorer.repo_index import RepoIndex
from llm_cst_refactorer.semantic import SemanticFunction
from llm_cst_refactorer.verification.pipeline import VerifierPipeline
from llm_cst_refactorer.verification.schema_verifier import verify_suggestion_schema


def test_fingerprint_stable() -> None:
    fn = SemanticFunction(qualified_name="add", source="def add(a, b):\n    return a + b\n")
    a = fn.with_fingerprint().fingerprint
    b = fn.with_fingerprint().fingerprint
    assert a == b
    assert len(a) == 64


def test_repo_index_neighbors(tmp_path: Path) -> None:
    mod = tmp_path / "mod.py"
    mod.write_text(
        "import os\n\n"
        "def helper(x: int) -> int:\n    return x\n\n"
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    index = RepoIndex([mod])
    collected = collect_functions(mod.read_text(encoding="utf-8"), file_path=str(mod.resolve()))
    fn = index.attach(collected[0].semantic)
    assert "helper" in fn.repo_context.neighboring_symbols or "os" in str(
        fn.repo_context.imported_names
    )
    assert fn.repo_context.convention_hints


def test_suggestion_confidence_filter() -> None:
    sug = Suggestion(
        param_types={
            "a": FieldSuggestion(value="int", confidence=0.9),
            "b": FieldSuggestion(value="str", confidence=0.2),
        },
        return_type=FieldSuggestion(value="int", confidence=0.8),
    )
    filtered = sug.filter_by_confidence(0.5)
    assert "a" in filtered.param_types
    assert "b" not in filtered.param_types
    assert filtered.return_type is not None


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = SuggestionCache(tmp_path / "cache")
    fn = SemanticFunction(
        qualified_name="add",
        source="def add(a, b):\n    return a + b\n",
    ).with_fingerprint()
    sug = Suggestion(param_types={"a": FieldSuggestion(value="int", confidence=0.9)})
    cache.put(fn, sug, engine="anthropic", model="x", plugin="typing-docstring")
    got = cache.get(fn, engine="anthropic", model="x", plugin="typing-docstring")
    assert got is not None
    assert got.param_types["a"].value == "int"


def test_metrics_report(tmp_path: Path) -> None:
    metrics = RunMetrics()
    metrics.llm_calls = 2
    metrics.verify_pass = 2
    metrics.finish()
    path = tmp_path / "report.json"
    metrics.write_json(path)
    assert path.is_file()
    assert "wall_seconds" in path.read_text(encoding="utf-8")


def test_verifier_pipeline_syntax_fail() -> None:
    result = VerifierPipeline().run("def broken(:\n")
    assert not result.ok
    assert result.stages[0].stage == "syntax"


def test_schema_verifier_bad_annotation() -> None:
    fn = collect_functions("def add(a, b):\n    return a + b\n")[0].semantic
    sug = Suggestion(param_types={"a": FieldSuggestion(value="not a type !!!", confidence=0.9)})
    result = verify_suggestion_schema(fn, sug)
    assert not result.ok
    assert result.stages[0].stage == "schema"


def test_plugin_factory() -> None:
    plugin = create_plugin("typing-docstring")
    assert plugin.name == "typing-docstring"
    with pytest.raises(ValueError):
        create_plugin("nope")


def test_create_plugins_and_init_return_none() -> None:
    from llm_cst_refactorer.plugins.factory import create_plugins
    from llm_cst_refactorer.plugins.init_return_none import InitReturnNonePlugin
    from llm_cst_refactorer.semantic import ParamInfo, SemanticFunction

    plugins = create_plugins("init-return-none,typing-docstring")
    assert [p.name for p in plugins] == ["init-return-none", "typing-docstring"]
    init_plugin = InitReturnNonePlugin()
    fn = SemanticFunction(
        qualified_name="Counter.__init__",
        source="def __init__(self, start):\n    self.value = start\n",
        params=[ParamInfo(name="self", is_self_or_cls=True), ParamInfo(name="start")],
        return_annotation=None,
    )
    assert init_plugin.select(fn)

    async def _run() -> None:
        sug = await init_plugin.propose(fn, provider=object())  # type: ignore[arg-type]
        assert sug.return_type is not None
        assert sug.return_type.value == "None"

    asyncio.run(_run())

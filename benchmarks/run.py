# SPDX-License-Identifier: AGPL-3.0-or-later
"""Offline precision benchmark (no live LLM).

Usage:
  poetry run python -m benchmarks.run
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from llm_cst_refactorer.collector import collect_functions
from llm_cst_refactorer.models import FieldSuggestion, Suggestion
from llm_cst_refactorer.semantic import SemanticFunction
from llm_cst_refactorer.transformer import apply_suggestion

ROOT = Path(__file__).resolve().parent
CASES = ROOT / "corpus" / "cases.json"


class OracleProvider:
    """Deterministic provider that returns corpus ground truth."""

    def __init__(self, truth: dict[str, object]) -> None:
        self.truth = truth

    async def suggest(
        self,
        fn: SemanticFunction,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        params = {
            name: FieldSuggestion(value=str(ann), confidence=1.0, evidence=["oracle"])
            for name, ann in (self.truth.get("param_types") or {}).items()  # type: ignore[union-attr]
            if name in fn.missing_param_names
        }
        ret = self.truth.get("return_type")
        docstring = None
        needles = self.truth.get("docstring_contains") or []
        if fn.needs.needs_docstring and needles:
            body = f"{needles[0]} function.\n\nArgs:\n    ...\n\nReturns:\n    ..."
            docstring = FieldSuggestion(value=body, confidence=1.0, evidence=["oracle"])
        return Suggestion(
            param_types=params,
            return_type=FieldSuggestion(value=str(ret), confidence=1.0) if ret else None,
            docstring=docstring,
        )


def score_case(case: dict[str, object]) -> dict[str, float]:
    source = str(case["source"])
    truth = case["truth"]  # type: ignore[assignment]
    assert isinstance(truth, dict)
    collected = collect_functions(source)
    if not collected:
        return {"param_precision": 0.0, "return_precision": 0.0, "doc_hit": 0.0}

    fn = collected[0].semantic
    # Synchronous oracle apply (no asyncio needed for scoring path)
    import asyncio

    provider = OracleProvider(truth)

    async def _run() -> Suggestion:
        return await provider.suggest(fn)

    suggestion = asyncio.run(_run())
    after = apply_suggestion(source, fn.qualified_name, suggestion)

    truth_params: dict[str, str] = truth.get("param_types") or {}  # type: ignore[assignment]
    correct = 0
    for name, expected in truth_params.items():
        if f"{name}: {expected}" in after:
            correct += 1
    param_precision = correct / len(truth_params) if truth_params else 1.0

    ret = truth.get("return_type")
    return_precision = 1.0 if ret and f"-> {ret}" in after else (1.0 if not ret else 0.0)

    needles = truth.get("docstring_contains") or []
    doc_hit = 1.0 if all(str(n).lower() in after.lower() for n in needles) else 0.0  # type: ignore[union-attr]

    return {
        "param_precision": param_precision,
        "return_precision": return_precision,
        "doc_hit": doc_hit,
    }


def main() -> int:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    scores = []
    for case in data["cases"]:
        s = score_case(case)
        scores.append(s)
        print(f"{case['id']}: {s}")

    n = len(scores) or 1
    avg = {
        key: sum(s[key] for s in scores) / n
        for key in ("param_precision", "return_precision", "doc_hit")
    }
    print(f"AVERAGE: {avg}")
    # Fail CI if oracle cannot hit perfect scores
    if avg["param_precision"] < 1.0 or avg["return_precision"] < 1.0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

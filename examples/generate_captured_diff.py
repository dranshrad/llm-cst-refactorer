# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate the golden captured dry-run diff for README (offline, no live LLM).

Usage:
  poetry run python examples/generate_captured_diff.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from llm_cst_refactorer.client import process_file  # noqa: E402
from llm_cst_refactorer.config import load_settings  # noqa: E402
from llm_cst_refactorer.diff_util import format_file_diff  # noqa: E402
from llm_cst_refactorer.models import FieldSuggestion, Suggestion  # noqa: E402
from llm_cst_refactorer.semantic import SemanticFunction  # noqa: E402

SAMPLE = ROOT / "examples" / "sample_legacy.py"
OUT = ROOT / "examples" / "captured" / "sample_legacy.unified.diff"


class CaptureProvider:
    """Deterministic provider used to capture a production-pipeline diff."""

    async def suggest(
        self,
        fn: SemanticFunction,
        *,
        repair_errors: str | None = None,
    ) -> Suggestion:
        _ = repair_errors
        params: dict[str, FieldSuggestion] = {}
        for name in fn.missing_param_names:
            value = "str"
            if name in {"times", "start", "step"}:
                value = "int"
            params[name] = FieldSuggestion(
                value=value, confidence=0.95, evidence=["capture-provider"]
            )
        return_type = None
        if fn.needs.needs_return:
            short = fn.qualified_name.rsplit(".", 1)[-1]
            if short == "__init__":
                ret_val = "None"
            elif short == "bump":
                ret_val = "int"
            else:
                ret_val = "str"
            return_type = FieldSuggestion(
                value=ret_val, confidence=0.95, evidence=["capture-provider"]
            )
        docstring = None
        if fn.needs.needs_docstring:
            docstring = FieldSuggestion(
                value=(
                    f"Auto-documented `{fn.qualified_name}`.\n\n"
                    "Args:\n"
                    "    See parameters.\n\n"
                    "Returns:\n"
                    "    See return value."
                ),
                confidence=0.9,
                evidence=["capture-provider"],
            )
        return Suggestion(param_types=params, return_type=return_type, docstring=docstring)


async def _main() -> int:
    settings = load_settings(apply=False, use_cache=False, max_retries=0, force=False)
    result = await process_file(SAMPLE, CaptureProvider(), settings)
    if not result.changed:
        print("No changes produced; aborting.", file=sys.stderr)
        for err in result.errors:
            print(err, file=sys.stderr)
        return 1
    # Stable paths in the golden file (relative)
    rel = "examples/sample_legacy.py"
    diff = format_file_diff(rel, result.before, result.after, color=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(diff, encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

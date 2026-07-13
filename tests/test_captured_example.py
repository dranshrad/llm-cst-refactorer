# SPDX-License-Identifier: AGPL-3.0-or-later
"""Golden test for the captured README dry-run example."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "examples" / "captured" / "sample_legacy.unified.diff"
GENERATOR = ROOT / "examples" / "generate_captured_diff.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_captured_diff", GENERATOR)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_captured_diff_matches_golden() -> None:
    assert GOLDEN.is_file(), "missing golden; run examples/generate_captured_diff.py"
    mod = _load_generator()
    from llm_cst_refactorer.client import process_file
    from llm_cst_refactorer.config import load_settings
    from llm_cst_refactorer.diff_util import format_file_diff

    settings = load_settings(apply=False, use_cache=False, max_retries=0, force=False)
    result = asyncio.run(process_file(mod.SAMPLE, mod.CaptureProvider(), settings))
    assert result.changed
    actual = format_file_diff("examples/sample_legacy.py", result.before, result.after, color=False)
    expected = GOLDEN.read_text(encoding="utf-8")
    assert actual == expected

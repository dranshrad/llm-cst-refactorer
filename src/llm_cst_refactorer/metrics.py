# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run metrics for timing, LLM usage, cache, and verification."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RunMetrics:
    """Accumulated metrics for a refactor run."""

    started_at: float = field(default_factory=time.perf_counter)
    ended_at: float | None = None
    llm_calls: int = 0
    llm_retries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    verify_pass: int = 0
    verify_fail: int = 0
    functions_skipped: int = 0
    functions_updated: int = 0
    files_changed: int = 0
    estimated_prompt_chars: int = 0
    estimated_completion_chars: int = 0
    stage_seconds: dict[str, float] = field(default_factory=dict)

    def add_stage(self, name: str, seconds: float) -> None:
        self.stage_seconds[name] = self.stage_seconds.get(name, 0.0) + seconds

    def finish(self) -> None:
        self.ended_at = time.perf_counter()

    @property
    def wall_seconds(self) -> float:
        end = self.ended_at if self.ended_at is not None else time.perf_counter()
        return max(0.0, end - self.started_at)

    @property
    def verification_success_rate(self) -> float:
        total = self.verify_pass + self.verify_fail
        return (self.verify_pass / total) if total else 0.0

    @property
    def estimated_tokens(self) -> int:
        # Rough heuristic: ~4 chars/token
        return (self.estimated_prompt_chars + self.estimated_completion_chars) // 4

    @property
    def estimated_cost_usd(self) -> float:
        # Conservative placeholder rate for reporting only
        return round(self.estimated_tokens * 0.000002, 6)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["wall_seconds"] = self.wall_seconds
        data["verification_success_rate"] = self.verification_success_rate
        data["estimated_tokens"] = self.estimated_tokens
        data["estimated_cost_usd"] = self.estimated_cost_usd
        return data

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def rich_summary(self) -> str:
        return (
            f"wall={self.wall_seconds:.2f}s "
            f"llm_calls={self.llm_calls} retries={self.llm_retries} "
            f"cache_hits={self.cache_hits}/{self.cache_hits + self.cache_misses} "
            f"verify_ok={self.verification_success_rate:.0%} "
            f"est_tokens≈{self.estimated_tokens} est_cost≈${self.estimated_cost_usd:.4f}"
        )

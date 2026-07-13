# SPDX-License-Identifier: AGPL-3.0-or-later
"""Filesystem suggestion cache keyed by SemanticFunction fingerprint."""

from __future__ import annotations

import json
from pathlib import Path

from llm_cst_refactorer.models import Suggestion
from llm_cst_refactorer.semantic import PROMPT_VERSION, SemanticFunction

DEFAULT_CACHE_DIR = Path(".llm_cst_cache")


class SuggestionCache:
    """JSON-on-disk cache for validated suggestions."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DEFAULT_CACHE_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def _key(
        self,
        fn: SemanticFunction,
        *,
        engine: str,
        model: str,
        plugin: str,
    ) -> str:
        fp = fn.fingerprint or fn.compute_fingerprint()
        raw = f"{fp}:{engine}:{model}:{plugin}:{PROMPT_VERSION}"
        # keep filename filesystem-safe
        import hashlib

        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(
        self,
        fn: SemanticFunction,
        *,
        engine: str,
        model: str,
        plugin: str,
    ) -> Suggestion | None:
        path = self._path(self._key(fn, engine=engine, model=model, plugin=plugin))
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Suggestion.model_validate(data)
        except (OSError, json.JSONDecodeError, ValueError):
            return None

    def put(
        self,
        fn: SemanticFunction,
        suggestion: Suggestion,
        *,
        engine: str,
        model: str,
        plugin: str,
    ) -> None:
        path = self._path(self._key(fn, engine=engine, model=model, plugin=plugin))
        path.write_text(suggestion.model_dump_json(indent=2), encoding="utf-8")

    def clear(self) -> int:
        """Delete all cache entries; return count removed."""
        count = 0
        if not self.root.is_dir():
            return 0
        for path in self.root.glob("*.json"):
            path.unlink(missing_ok=True)
            count += 1
        return count

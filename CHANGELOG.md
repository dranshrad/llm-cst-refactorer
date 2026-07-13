# Changelog

All notable changes to this project will be documented in this file.

## [0.2.2] — 2026-07-14

### Changed

- OpenAI default model updated to `gpt-5.6-luna` (document `gpt-5.6-terra` / `gpt-5.6-sol` overrides)
- Repository URLs corrected to `dranshrad/llm-cst-refactorer`

## [0.2.1] — 2026-07-14

### Fixed

- Default model IDs updated to current generations: `claude-sonnet-5`, `gpt-5-mini`
- README before/after replaced with a pipeline-captured golden unified diff
- Incremental mypy verification no longer fails on sibling untyped defs mid-refactor

### Added

- `init-return-none` deterministic plugin (`-> None` on `__init__`)
- Comma-separated `--plugin` lists (default: `init-return-none,typing-docstring`)
- `examples/generate_captured_diff.py` + `examples/captured/sample_legacy.unified.diff`
- Golden test for the captured README example

## [0.2.0] — 2026-07-14

### Added

- `SemanticFunction` intermediate representation with fingerprints
- `RepoIndex` for imports, neighbors, and convention hints before LLM calls
- Structured suggestion fields with `confidence` + `evidence` (legacy string JSON still accepted)
- Multi-stage `VerifierPipeline` (syntax → schema → mypy) with stage-tagged repair
- Stable `RefactorPlugin` API (`typing-docstring` default) and `--plugin`
- Filesystem suggestion cache (`.llm_cst_cache/`) with `--no-cache` / `--refresh-cache`
- `RunMetrics` + `--report PATH.json` + Rich summary line
- Offline `benchmarks/` corpus runner
- README repositioned as an AI semantic transformation engine

### Changed

- Version bump to 0.2.0
- Providers and prompts consume `SemanticFunction` instead of flat `FunctionContext`

## [0.1.0] — 2026-07-14

### Added

- Initial public release: LibCST pipeline, pluggable providers, mypy gate, dry-run diffs, AGPL-3.0-or-later

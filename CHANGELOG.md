# Changelog

All notable changes to this project will be documented in this file.

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

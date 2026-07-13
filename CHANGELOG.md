# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] — 2026-07-14

### Added

- Initial public release scaffold for the LLM Docstring & Typing Auto-Refactorer
- LibCST collector + transformer pipeline for missing types and Google-style docstrings
- Pluggable providers: Anthropic, OpenAI, OpenAI-compatible (`base_url`)
- mypy verification gate with repair retries
- Dry-run unified diffs (colorized); `--apply` to write
- Typer CLI, Poetry packaging, Ruff/mypy/pytest CI
- AGPL-3.0-or-later license

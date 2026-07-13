# Contributing

Thanks for helping improve **llm-cst-refactorer**.

## Development setup

1. Install Python 3.11+ and [Poetry](https://python-poetry.org/).
2. Clone the repository and install deps:

```bash
poetry install
```

3. Copy `.env.example` to `.env` if you need live provider smoke tests (CI never calls paid APIs).

## Checks before opening a PR

```bash
poetry run ruff check src tests
poetry run ruff format src tests
poetry run mypy
poetry run pytest
```

## Guidelines

- Prefer LibCST node surgery over string rewriting.
- Prefer extending `SemanticFunction` / `RefactorPlugin` over special-case CLI logic.
- Keep dry-run the safe default; never write without `--apply`.
- Mock LLM providers in unit tests — no network calls in CI.
- Add SPDX headers: `# SPDX-License-Identifier: AGPL-3.0-or-later`
- Keep public APIs fully typed.
- Plugin API version is `"1"` — bump deliberately and document breaking changes.

## License

Contributions are accepted under **AGPL-3.0-or-later** (see [LICENSE](LICENSE)).

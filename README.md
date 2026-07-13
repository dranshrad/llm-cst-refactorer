# LLM Docstring & Typing Auto-Refactorer

Format-preserving Python refactorer that adds **missing type hints** and **Google-style docstrings** using [LibCST](https://libcst.readthedocs.io/) and an LLM — without destroying comments, spacing, or layout the way a naive AST round-trip would.

Licensed under the **GNU Affero General Public License v3 or later (AGPL-3.0-or-later)**.

## Why LibCST?

Regex and string splicing break syntax. `ast` is safe to *read* but rewriting with `ast.unparse` drops formatting and comments. **LibCST** keeps the concrete syntax tree intact and only mutates the nodes you target.

## Features

- **CST transformers** — observe with a visitor, apply with `CSTTransformer`
- **Pluggable LLM engines** — Anthropic, OpenAI, or OpenAI-compatible (`base_url` for Ollama / vLLM / LocalAI)
- **mypy gate** — generated annotations are verified before write (repair retries supported)
- **Dry-run by default** — Git-style colored unified diffs; require `--apply` to write
- **Skip markers** — `# llm-cst: skip` or `# noqa: llm-cst` on/above a definition
- **Strict packaging** — Poetry, Ruff, mypy strict, pytest CI

## Install (from source)

Requires Python 3.11+.

```bash
git clone https://github.com/divyanshgupta/llm-cst-refactorer.git
cd llm-cst-refactorer
poetry install
poetry run llm-cst-refactor --help
```

Editable install without Poetry:

```bash
pip install -e ".[dev]"   # after exporting/using pyproject extras, or: poetry export
```

PyPI publishing is prepared via `pyproject.toml` metadata but **not published** in this initial release.

## Quickstart

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY or OPENAI_API_KEY

# Preview only (default)
poetry run llm-cst-refactor examples/sample_legacy.py --engine anthropic

# Write changes
poetry run llm-cst-refactor examples/sample_legacy.py --engine anthropic --apply
```

Example dry-run output shape:

```diff
--- a/examples/sample_legacy.py
+++ b/examples/sample_legacy.py
@@ -1,6 +1,12 @@
-def greet(name, times=1):
+def greet(name: str, times: int = 1) -> str:
+    """Return a repeated greeting.
+
+    Args:
+        name: Person to greet.
+        times: Repetition count.
+    """
     # Preserve this comment when refactoring.
     return ("hello " + name + "! ") * times
```

## Providers

| `--engine`     | Auth                         | Notes |
|----------------|------------------------------|-------|
| `anthropic`    | `ANTHROPIC_API_KEY`          | Default model `claude-sonnet-4-20250514` |
| `openai`       | `OPENAI_API_KEY`             | Default model `gpt-4.1-mini` |
| `compatible`   | `OPENAI_API_KEY` (optional)  | Requires `--base-url` / `LLM_CST_BASE_URL` |

Ollama example:

```bash
export LLM_CST_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
poetry run llm-cst-refactor ./src --engine compatible --model llama3.2
```

## CLI

```text
llm-cst-refactor PATH
  --engine anthropic|openai|compatible
  --model TEXT
  --base-url TEXT
  --apply / --dry-run          # dry-run is the default
  --concurrency INT
  --include / --exclude GLOB
  --docstring-style google
  --types-only / --docs-only
  --max-retries INT
  --force                      # skip mypy (discouraged)
  --verbose
```

Env vars: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LLM_CST_BASE_URL`, `LLM_CST_ENGINE`, `LLM_CST_MODEL`.

## Safety model

1. **Dry-run default** — nothing is written unless `--apply`
2. **mypy verification** — per-function candidates and a final whole-file check
3. **Skip comments** — opt out of specific definitions
4. **Structured JSON** — LLM must return validated `Suggestion` payloads

## Architecture

```text
scan → LibCST collect → LLM suggest → mypy verify → CST apply → diff / write
```

## Development

```bash
poetry install
poetry run ruff check src tests
poetry run ruff format src tests
poetry run mypy
poetry run pytest
```

## Roadmap (not in v1)

- Class attribute inference
- Stub (`.pyi`) emission
- Additional docstring styles
- CI bot / PR review mode

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). By contributing, you agree that your contributions are licensed under AGPL-3.0-or-later.

## License

This project is free software under the [GNU Affero General Public License v3.0 or later](LICENSE).

If you modify this program and provide it to users over a network (including as a hosted service), AGPL requires that you also provide them the corresponding source under the same license.

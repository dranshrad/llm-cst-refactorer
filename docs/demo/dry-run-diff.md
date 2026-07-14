# Demo: dry-run unified diff

```bash
poetry run llm-cst-refactor examples/sample_legacy.py --dry-run
# or inspect the golden capture:
# cat examples/captured/sample_legacy.unified.diff
```

```bash
asciinema play docs/demo/dry-run-diff.cast
```

Regenerate the README GIF (requires [`agg`](https://github.com/asciinema/agg)):

```bash
agg --speed 1.5 --font-size 14 --theme monokai docs/demo/dry-run-diff.cast docs/demo/dry-run-diff.gif
```

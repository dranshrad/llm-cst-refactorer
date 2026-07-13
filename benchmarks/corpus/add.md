# Offline micro-benchmark corpus for typing/docstring precision.

## Source under test
```python
def add(a, b):
    return a + b
```

## Ground truth
```json
{
  "param_types": {"a": "int", "b": "int"},
  "return_type": "int",
  "docstring_contains": ["Add", "Args", "Returns"]
}
```

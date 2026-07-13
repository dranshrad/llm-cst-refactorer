# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for provider factory and JSON parsing with confidence."""

from __future__ import annotations

import pytest

from llm_cst_refactorer.config import Engine, load_settings
from llm_cst_refactorer.prompts import parse_suggestion_json
from llm_cst_refactorer.providers.factory import create_provider
from llm_cst_refactorer.providers.openai_provider import OpenAIProvider


def test_parse_suggestion_json_plain_and_fenced() -> None:
    plain = '{"param_types": {"a": "int"}, "return_type": "int", "docstring": "Add."}'
    sug = parse_suggestion_json(plain)
    assert sug.param_types["a"].value == "int"
    assert sug.param_types["a"].confidence == 0.7
    assert sug.return_type is not None
    assert sug.return_type.value == "int"

    fenced = '```json\n{"param_types": {}, "return_type": null, "docstring": null}\n```'
    sug2 = parse_suggestion_json(fenced)
    assert sug2.return_type is None


def test_parse_structured_confidence() -> None:
    raw = """{
      "param_types": {
        "a": {"value": "int", "confidence": 0.95, "evidence": ["literal add"]}
      },
      "return_type": {"value": "int", "confidence": 0.9, "evidence": ["return a+b"]},
      "docstring": null
    }"""
    sug = parse_suggestion_json(raw)
    assert sug.param_types["a"].confidence == 0.95
    assert sug.param_types["a"].evidence == ["literal add"]


def test_compatible_requires_base_url() -> None:
    settings = load_settings(engine="compatible", model="llama3.2")
    with pytest.raises(ValueError, match="base-url"):
        create_provider(settings)


def test_compatible_provider_uses_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "ollama")
    settings = load_settings(
        engine="compatible",
        model="llama3.2",
        base_url="http://localhost:11434/v1",
    )
    provider = create_provider(settings)
    assert isinstance(provider, OpenAIProvider)
    assert settings.engine is Engine.COMPATIBLE
    assert settings.base_url == "http://localhost:11434/v1"


def test_anthropic_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    settings = load_settings(engine="anthropic")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        create_provider(settings)

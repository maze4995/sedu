"""Tests for variant/hint generation fallbacks."""

from __future__ import annotations

from app.services.hint_generator import generate_hint
from app.services.variant_generator import generate_variant


def _parsed_v1() -> dict:
    return {
        "stem": "다음 중 에너지 전환의 예로 옳은 것은?",
        "clean_text_preview": "다음 중 에너지 전환의 예로 옳은 것은? 1) 전구 2) 광합성",
        "choices": [
            {"label": "1", "text": "전구"},
            {"label": "2", "text": "광합성"},
        ],
    }


def test_generate_variant_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    payload, model = generate_variant(_parsed_v1(), variant_type="paraphrase")

    assert model == "rule_based_v1"
    assert payload["variant_type"] == "paraphrase"
    assert payload["body"]
    assert "explanation" in payload


def test_generate_hint_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    payload, model = generate_hint(
        parsed=_parsed_v1(),
        recent_chat=[{"role": "user", "text": "어떻게 시작하죠?"}],
        level="weak",
        stroke_summary=None,
    )

    assert model == "rule_based_v1"
    assert payload["level"] == "weak"
    assert payload["hint"]

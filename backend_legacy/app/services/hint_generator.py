"""Hint generation service (Gemini-first with deterministic fallback)."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.core.env import load_backend_env
from app.gemini.client import call_gemini_structured

_DEFAULT_HINT_MODEL = "gemini-2.5-flash"
_VALID_LEVELS = {"weak", "medium", "strong"}
logger = logging.getLogger(__name__)

_HINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["level", "hint"],
    "additionalProperties": False,
    "properties": {
        "level": {"type": "string", "enum": ["weak", "medium", "strong"]},
        "hint": {"type": "string"},
    },
}


def _coerce_level(level: str | None) -> str:
    if isinstance(level, str) and level in _VALID_LEVELS:
        return level
    return "weak"


def _rule_based_hint(parsed: dict[str, Any], level: str) -> str:
    stem = str(parsed.get("stem") or "").strip()
    preview = str(parsed.get("clean_text_preview") or stem).strip()
    base = preview or "문제의 핵심 조건을 먼저 정리해보세요."

    if level == "weak":
        return f"핵심 조건 1~2개를 표시해보세요: {base[:80]}"
    if level == "medium":
        return f"단원을 떠올려 풀이 전략을 고르세요. 먼저 {base[:100]}를 기준으로 식/개념을 매칭해보세요."
    return f"강한 힌트: 문제를 작은 단계로 나누고, 각 단계에서 필요한 개념을 명시하세요. 출발점은 '{base[:120]}' 입니다."


def _build_prompt(
    *,
    parsed: dict[str, Any],
    recent_chat: list[dict[str, str]],
    level: str,
    stroke_summary: str | None,
) -> tuple[str, str]:
    system = (
        "You are a Korean high-school science tutor. "
        "Return one concise hint in JSON only."
    )
    user = (
        f"target_level: {level}\n"
        f"question_parsed_v1: {parsed}\n"
        f"recent_chat: {recent_chat}\n"
        f"stroke_summary: {stroke_summary or ''}\n"
        "Return JSON with fields: level, hint."
    )
    return system, user


def generate_hint(
    *,
    parsed: dict[str, Any],
    recent_chat: list[dict[str, str]],
    level: str | None,
    stroke_summary: str | None,
) -> tuple[dict[str, str], str]:
    if not isinstance(parsed, dict):
        raise ValueError("parsed_v1 is required for hint generation")

    selected_level = _coerce_level(level)
    load_backend_env()
    model_name = os.getenv("GEMINI_HINT_MODEL", os.getenv("GEMINI_MODEL", _DEFAULT_HINT_MODEL))
    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        system, user = _build_prompt(
            parsed=parsed,
            recent_chat=recent_chat,
            level=selected_level,
            stroke_summary=stroke_summary,
        )
        try:
            data = call_gemini_structured(
                model_name=model_name,
                system=system,
                user=user,
                response_schema=_HINT_SCHEMA,
            )
            hint = str(data.get("hint") or "").strip()
            level_resp = _coerce_level(str(data.get("level") or selected_level))
            if hint:
                return {"level": level_resp, "hint": hint}, model_name
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini hint generation failed: %s", exc)

    return {
        "level": selected_level,
        "hint": _rule_based_hint(parsed, selected_level),
    }, "rule_based_v1"

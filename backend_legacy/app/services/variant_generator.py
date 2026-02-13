"""Variant generation service (Gemini-first with deterministic fallback)."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.core.env import load_backend_env
from app.gemini.client import call_gemini_structured

_DEFAULT_VARIANT_MODEL = "gemini-2.5-flash"
logger = logging.getLogger(__name__)

_VARIANT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["variant_type", "body", "answer", "explanation"],
    "additionalProperties": False,
    "properties": {
        "variant_type": {"type": "string"},
        "body": {"type": "string"},
        "answer": {"type": "string"},
        "explanation": {"type": "string"},
    },
}


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _build_rule_based_variant(parsed: dict[str, Any], variant_type: str) -> dict[str, str]:
    stem = _coerce_text(parsed.get("stem")) or "문제 본문을 확인하세요."
    choices = parsed.get("choices") if isinstance(parsed.get("choices"), list) else []
    choices_text: list[str] = []
    answer = ""

    for choice in choices:
        if not isinstance(choice, dict):
            continue
        label = _coerce_text(choice.get("label"))
        text = _coerce_text(choice.get("text"))
        if label or text:
            choices_text.append(f"{label}) {text}".strip())
        if not answer and label:
            answer = label

    body_lines = [f"[{variant_type}] {stem}"]
    if choices_text:
        body_lines.append("")
        body_lines.extend(choices_text)

    return {
        "variant_type": variant_type,
        "body": "\n".join(body_lines).strip(),
        "answer": answer or "확인 필요",
        "explanation": "원문항의 핵심 개념을 유지한 변형 문제입니다.",
    }


def _build_gemini_prompt(parsed: dict[str, Any], variant_type: str) -> tuple[str, str]:
    system = (
        "You generate one Korean science question variant JSON. "
        "Keep the same learning objective and return only valid JSON."
    )
    user = (
        f"variant_type: {variant_type}\n"
        "source_question_parsed_v1:\n"
        f"{parsed}\n"
        "Return JSON with fields: variant_type, body, answer, explanation."
    )
    return system, user


def generate_variant(parsed: dict[str, Any], *, variant_type: str) -> tuple[dict[str, str], str]:
    """Generate one variant and return (payload, model_used)."""
    if not isinstance(parsed, dict):
        raise ValueError("parsed_v1 is required for variant generation")

    load_backend_env()
    model_name = os.getenv("GEMINI_VARIANT_MODEL", os.getenv("GEMINI_MODEL", _DEFAULT_VARIANT_MODEL))
    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        system, user = _build_gemini_prompt(parsed, variant_type)
        try:
            data = call_gemini_structured(
                model_name=model_name,
                system=system,
                user=user,
                response_schema=_VARIANT_SCHEMA,
            )
            if all(isinstance(data.get(k), str) for k in ("variant_type", "body", "answer", "explanation")):
                return {
                    "variant_type": _coerce_text(data["variant_type"]) or variant_type,
                    "body": _coerce_text(data["body"]),
                    "answer": _coerce_text(data["answer"]),
                    "explanation": _coerce_text(data["explanation"]),
                }, model_name
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gemini variant generation failed: %s", exc)

    return _build_rule_based_variant(parsed, variant_type), "rule_based_v1"

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.domain.models import QuestionRecord
from app.infra.ports.llm import LLMPort

_HINT_LEVELS = {"weak", "medium", "strong"}
_VARIANT_TYPES = {"paraphrase", "numeric_swap", "concept_shift", "format_transform"}

_VARIANT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["variantType", "body", "answer", "explanation"],
    "properties": {
        "variantType": {"type": "string"},
        "body": {"type": "string"},
        "answer": {"type": "string"},
        "explanation": {"type": "string"},
        "model": {"type": "string"},
    },
}

_HINT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["level", "hint"],
    "properties": {
        "level": {"type": "string", "enum": ["weak", "medium", "strong"]},
        "hint": {"type": "string"},
        "model": {"type": "string"},
    },
}


class VariantStorePort(Protocol):
    def create_variant_for_question(
        self,
        *,
        question_id: str,
        variant_type: str,
        body: str,
        answer: str | None,
        explanation: str | None,
        model: str | None,
    ):
        ...


@dataclass
class VariantResult:
    variant_type: str
    body: str
    answer: str
    explanation: str
    model: str


@dataclass
class HintResult:
    level: str
    hint: str
    model: str


def _coerce_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _extract_context(question: QuestionRecord) -> dict[str, Any]:
    parsed = {}
    if isinstance(question.structure, dict):
        maybe = question.structure.get("parsed_v1")
        if isinstance(maybe, dict):
            parsed = dict(maybe)

    stem = _coerce_text(parsed.get("stem")) or _coerce_text(question.ocr_text) or "문항 원문"
    choices = parsed.get("choices") if isinstance(parsed.get("choices"), list) else []
    normalized_choices: list[dict[str, str]] = []
    for item in choices:
        if not isinstance(item, dict):
            continue
        label = _coerce_text(item.get("label"))
        text = _coerce_text(item.get("text"))
        if label or text:
            normalized_choices.append({"label": label, "text": text})

    answer_hint = ""
    if isinstance(question.metadata, dict):
        answer_hint = _coerce_text(question.metadata.get("answer")) or _coerce_text(question.metadata.get("answerKey"))

    return {
        "stem": stem,
        "choices": normalized_choices,
        "answer_hint": answer_hint,
        "metadata": question.metadata if isinstance(question.metadata, dict) else {},
    }


def _rule_based_variant(*, context: dict[str, Any], variant_type: str) -> VariantResult:
    stem = _coerce_text(context.get("stem")) or "문제 본문을 확인하세요."
    choices = context.get("choices") if isinstance(context.get("choices"), list) else []
    answer_hint = _coerce_text(context.get("answer_hint"))

    body_lines = [f"[{variant_type}] {stem}"]
    if choices:
        body_lines.append("")
        for item in choices:
            if not isinstance(item, dict):
                continue
            label = _coerce_text(item.get("label")) or "?"
            text = _coerce_text(item.get("text"))
            body_lines.append(f"{label}) {text}".rstrip())

    answer = answer_hint
    if not answer and choices:
        first = choices[0]
        if isinstance(first, dict):
            answer = _coerce_text(first.get("label"))
    if not answer:
        answer = "확인 필요"

    return VariantResult(
        variant_type=variant_type,
        body="\n".join(body_lines).strip(),
        answer=answer,
        explanation="원문항의 학습목표를 유지하는 규칙기반 변형입니다.",
        model="rule_based_v2",
    )


def _rule_based_hint(*, context: dict[str, Any], level: str) -> HintResult:
    stem = _coerce_text(context.get("stem"))
    preview = stem[:100] if stem else "핵심 조건을 먼저 정리해보세요."

    if level == "medium":
        hint = f"조건을 식/개념으로 바꾼 뒤 보기와 하나씩 대조해보세요. 시작점: {preview}"
    elif level == "strong":
        hint = f"강한 힌트: 오답 조건을 먼저 제거하고 남은 경우를 검산하세요. 기준 문장: {preview}"
    else:
        hint = f"핵심 조건 1~2개를 먼저 표시해보세요. 출발점: {preview}"

    return HintResult(level=level, hint=hint.strip(), model="rule_based_v2")


class AIGenerationService:
    def __init__(self, *, llm: LLMPort, store: VariantStorePort):
        self.llm = llm
        self.store = store

    def create_variant(self, *, question: QuestionRecord, variant_type: str):
        context = _extract_context(question)
        provider_model = getattr(self.llm, "model_name", None) or "llm"

        system = (
            "You are an assistant that generates Korean exam variants. "
            "Output must be strict JSON only."
        )
        prompt = (
            f"variantType={variant_type}\n"
            f"question={json.dumps(context, ensure_ascii=False)}\n"
            "Create one variant with same learning objective."
        )

        result: VariantResult | None = None
        try:
            data = self.llm.generate_structured(
                prompt=prompt,
                schema=_VARIANT_SCHEMA,
                system_prompt=system,
            )
            body = _coerce_text(data.get("body"))
            answer = _coerce_text(data.get("answer"))
            explanation = _coerce_text(data.get("explanation"))
            variant_resp_type = _coerce_text(data.get("variantType")) or variant_type
            if variant_resp_type not in _VARIANT_TYPES:
                variant_resp_type = variant_type
            model = _coerce_text(data.get("model")) or provider_model
            if body and answer and explanation:
                result = VariantResult(
                    variant_type=variant_resp_type,
                    body=body,
                    answer=answer,
                    explanation=explanation,
                    model=model,
                )
        except Exception:
            result = None

        if result is None:
            result = _rule_based_variant(context=context, variant_type=variant_type)

        return self.store.create_variant_for_question(
            question_id=question.question_id,
            variant_type=result.variant_type,
            body=result.body,
            answer=result.answer,
            explanation=result.explanation,
            model=result.model,
        )

    def create_hint(
        self,
        *,
        question: QuestionRecord,
        level: str,
        recent_chat: list[dict[str, str]],
        stroke_summary: str | None,
    ) -> HintResult:
        selected_level = level if level in _HINT_LEVELS else "weak"
        context = _extract_context(question)
        provider_model = getattr(self.llm, "model_name", None) or "llm"
        system = (
            "You are a Korean science tutor. "
            "Return one concise hint in strict JSON format."
        )
        prompt = (
            f"target_level={selected_level}\n"
            f"question={json.dumps(context, ensure_ascii=False)}\n"
            f"recent_chat={json.dumps(recent_chat, ensure_ascii=False)}\n"
            f"stroke_summary={stroke_summary or ''}\n"
        )

        try:
            data = self.llm.generate_structured(
                prompt=prompt,
                schema=_HINT_SCHEMA,
                system_prompt=system,
            )
            hint = _coerce_text(data.get("hint"))
            level_resp = _coerce_text(data.get("level"))
            model = _coerce_text(data.get("model")) or provider_model
            if hint:
                if level_resp not in _HINT_LEVELS:
                    level_resp = selected_level
                return HintResult(level=level_resp, hint=hint, model=model)
        except Exception:
            pass

        return _rule_based_hint(context=context, level=selected_level)

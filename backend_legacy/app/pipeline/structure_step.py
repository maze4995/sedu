"""Gemini structuring step for OCR-extracted questions."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.env import load_backend_env
from app.gemini.client import call_gemini_structured
from app.gemini.render import render_question_structure_prompt, render_segmentation_qc_prompt
from app.gemini.validate import (
    SchemaValidationError,
    validate_question_structure,
    validate_segmentation_qc,
)

_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "gemini" / "schemas" / "question_structure.v1.json"
)
_SEGMENTATION_QC_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "gemini" / "schemas" / "segmentation_qc.v1.json"
)
_DEFAULT_MODEL = "gemini-2.5-flash"
_MAX_ERROR_MESSAGE = 800
_STRICT_REVIEW_STATUSES = {"approved", "rejected"}


def _load_question_structure_schema() -> dict[str, Any]:
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_segmentation_qc_schema() -> dict[str, Any]:
    with open(_SEGMENTATION_QC_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _get_question_bbox(question_row) -> dict[str, Any]:
    metadata = getattr(question_row, "metadata_json", None) or {}
    candidate = metadata.get("question_bbox")
    if isinstance(candidate, dict):
        return candidate
    return {}


def _get_source_page(question_row) -> int:
    metadata = getattr(question_row, "metadata_json", None) or {}
    candidate = metadata.get("source_page")
    if isinstance(candidate, int):
        return candidate
    return 0


def build_structure_input(question_row) -> dict[str, str]:
    """Build placeholder values used by Gemini prompt templates."""
    structure = getattr(question_row, "structure", None) or {}
    tokens = structure.get("ocr_tokens") if isinstance(structure, dict) else None
    if not isinstance(tokens, list):
        tokens = []

    set_public_id = ""
    if getattr(question_row, "set", None) is not None:
        set_public_id = str(getattr(question_row.set, "public_id", "") or "")
    if not set_public_id:
        metadata = getattr(question_row, "metadata_json", None) or {}
        set_public_id = str(metadata.get("set_public_id", "") or "")

    return {
        "setId": set_public_id,
        "questionId": str(question_row.public_id),
        "pageNo": str(_get_source_page(question_row)),
        "questionBBox": _json_dumps(_get_question_bbox(question_row)),
        "ocrTokensJson": _json_dumps(tokens),
        "assetsJson": _json_dumps([]),
        "nearbyTokensJson": _json_dumps([]),
    }


def _truncate_error_message(message: str) -> str:
    msg = (message or "").strip()
    if len(msg) <= _MAX_ERROR_MESSAGE:
        return msg
    return msg[:_MAX_ERROR_MESSAGE] + "..."


def _mark_error(question_row, err_type: str, message: str) -> None:
    metadata = dict(getattr(question_row, "metadata_json", None) or {})
    metadata["structure_error"] = {
        "type": err_type,
        "message": _truncate_error_message(message),
    }
    question_row.metadata_json = metadata

    if getattr(question_row, "review_status", None) not in _STRICT_REVIEW_STATUSES:
        question_row.review_status = "auto_flagged"


def _run_segmentation_qc(question_row, *, model_name: str) -> None:
    prompt_input = build_structure_input(question_row)
    rendered = render_segmentation_qc_prompt(prompt_input)
    schema = _load_segmentation_qc_schema()

    try:
        result = call_gemini_structured(
            model_name=model_name,
            system=rendered["system"],
            user=rendered["user"],
            response_schema=schema,
        )
        validated = validate_segmentation_qc(result)
        validated_dict = validated.model_dump(mode="json")

        structure = dict(getattr(question_row, "structure", None) or {})
        structure["segmentation_qc_v1"] = validated_dict
        question_row.structure = structure

        metadata = dict(getattr(question_row, "metadata_json", None) or {})
        metadata["segmentation_qc_model"] = model_name
        metadata["segmentation_qc_at"] = datetime.now(timezone.utc).isoformat()
        metadata.pop("segmentation_qc_error", None)
        question_row.metadata_json = metadata

        has_issues = bool(validated.issues)
        if not validated.is_complete or has_issues:
            if getattr(question_row, "review_status", None) not in _STRICT_REVIEW_STATUSES:
                question_row.review_status = "auto_flagged"
    except Exception as exc:  # noqa: BLE001
        metadata = dict(getattr(question_row, "metadata_json", None) or {})
        metadata["segmentation_qc_error"] = {
            "type": type(exc).__name__,
            "message": _truncate_error_message(str(exc)),
        }
        question_row.metadata_json = metadata
        if getattr(question_row, "review_status", None) not in _STRICT_REVIEW_STATUSES:
            question_row.review_status = "auto_flagged"


def run_gemini_structuring(db: Session, question_row) -> None:
    """Run Gemini structuring for one question and persist result."""
    load_backend_env()
    model_name = os.getenv("GEMINI_MODEL", _DEFAULT_MODEL)
    _run_segmentation_qc(question_row, model_name=model_name)
    prompt_input = build_structure_input(question_row)
    rendered = render_question_structure_prompt(prompt_input)
    schema = _load_question_structure_schema()

    last_error: Exception | None = None
    for _ in range(2):  # first try + one retry
        try:
            result = call_gemini_structured(
                model_name=model_name,
                system=rendered["system"],
                user=rendered["user"],
                response_schema=schema,
            )
            validated = validate_question_structure(result)
            validated_dict = validated.model_dump(mode="json")

            structure = dict(getattr(question_row, "structure", None) or {})
            structure["parsed_v1"] = validated_dict
            question_row.structure = structure

            metadata = dict(getattr(question_row, "metadata_json", None) or {})
            metadata["structure_model"] = model_name
            metadata["structured_at"] = datetime.now(timezone.utc).isoformat()
            metadata.pop("structure_error", None)
            question_row.metadata_json = metadata

            if validated.review.needs_review:
                if getattr(question_row, "review_status", None) not in _STRICT_REVIEW_STATUSES:
                    question_row.review_status = "auto_flagged"
            elif getattr(question_row, "review_status", None) == "unreviewed":
                question_row.review_status = "auto_ok"

            db.add(question_row)
            db.commit()
            db.refresh(question_row)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    if last_error is not None:
        err_type = type(last_error).__name__
        if isinstance(last_error, SchemaValidationError):
            err_type = "SchemaValidationError"
        _mark_error(question_row, err_type, str(last_error))
        db.add(question_row)
        db.commit()
        db.refresh(question_row)

"""Schema validation: jsonschema first, then Pydantic parsing."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import jsonschema
from pydantic import ValidationError

from app.gemini.types import QuestionStructureV1, SegmentationQCV1

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


class SchemaValidationError(Exception):
    """Raised when Gemini output fails schema or model validation."""


@lru_cache(maxsize=4)
def _load_schema(name: str) -> dict:
    path = _SCHEMA_DIR / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate_json_schema(data: dict, schema_name: str) -> None:
    schema = _load_schema(schema_name)
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise SchemaValidationError(
            f"JSON Schema validation failed ({schema_name}): {exc.message}"
        ) from exc


def validate_question_structure(data: dict) -> QuestionStructureV1:
    """Validate data against question_structure.v1.json then parse into Pydantic."""
    _validate_json_schema(data, "question_structure.v1.json")
    try:
        return QuestionStructureV1.model_validate(data)
    except ValidationError as exc:
        raise SchemaValidationError(
            f"Pydantic validation failed (QuestionStructureV1): {exc}"
        ) from exc


def validate_segmentation_qc(data: dict) -> SegmentationQCV1:
    """Validate data against segmentation_qc.v1.json then parse into Pydantic."""
    _validate_json_schema(data, "segmentation_qc.v1.json")
    try:
        return SegmentationQCV1.model_validate(data)
    except ValidationError as exc:
        raise SchemaValidationError(
            f"Pydantic validation failed (SegmentationQCV1): {exc}"
        ) from exc

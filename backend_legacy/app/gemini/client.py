"""Gemini structured-output call wrapper via Google AI API (ai.google.dev)."""

from __future__ import annotations

import json
import logging
import os
from urllib import error as urlerror
from urllib import parse, request

from app.core.env import load_backend_env

logger = logging.getLogger(__name__)

_GOOGLE_AI_BASE = "https://generativelanguage.googleapis.com/v1beta"
_TYPE_MAP = {
    "object": "OBJECT",
    "array": "ARRAY",
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "null": "NULL",
}


def _normalize_schema_type(type_value) -> tuple[str | None, bool]:
    """Convert JSON Schema type(s) to Gemini schema type + nullable flag."""
    if isinstance(type_value, str):
        mapped = _TYPE_MAP.get(type_value.lower())
        return mapped, False

    if isinstance(type_value, list):
        types = [t for t in type_value if isinstance(t, str)]
        nullable = any(t.lower() == "null" for t in types)
        non_null = [t for t in types if t.lower() != "null"]
        if not non_null:
            return None, nullable
        mapped = _TYPE_MAP.get(non_null[0].lower())
        return mapped, nullable

    return None, False


def _to_gemini_response_schema(node):
    """Convert generic JSON Schema into Gemini REST responseSchema subset.

    Gemini REST rejects keys such as ``$schema``, ``$id``,
    ``additionalProperties``.
    """
    if not isinstance(node, dict):
        return {}

    out: dict = {}

    mapped_type, nullable_from_type = _normalize_schema_type(node.get("type"))
    if mapped_type:
        out["type"] = mapped_type
    if nullable_from_type:
        out["nullable"] = True
    elif isinstance(node.get("nullable"), bool):
        out["nullable"] = node["nullable"]

    if isinstance(node.get("description"), str):
        out["description"] = node["description"]
    if isinstance(node.get("format"), str):
        out["format"] = node["format"]

    if isinstance(node.get("enum"), list):
        out["enum"] = node["enum"]

    if isinstance(node.get("required"), list):
        out["required"] = [k for k in node["required"] if isinstance(k, str)]

    properties = node.get("properties")
    if isinstance(properties, dict):
        out["properties"] = {
            key: _to_gemini_response_schema(value)
            for key, value in properties.items()
            if isinstance(key, str) and isinstance(value, dict)
        }

    items = node.get("items")
    if isinstance(items, dict):
        out["items"] = _to_gemini_response_schema(items)
    elif isinstance(items, list) and items:
        # Tuple typing is not supported by Gemini responseSchema.
        first = items[0]
        if isinstance(first, dict):
            out["items"] = _to_gemini_response_schema(first)

    return out


def call_gemini_structured(
    *,
    model_name: str,
    system: str,
    user: str,
    response_schema: dict,
) -> dict:
    """Call Gemini and return JSON parsed from structured output."""
    load_backend_env()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is required. "
            "Get one at https://aistudio.google.com/apikey"
        )

    url = (
        f"{_GOOGLE_AI_BASE}/models/{parse.quote(model_name)}:generateContent"
        f"?key={parse.quote(api_key)}"
    )
    gemini_schema = _to_gemini_response_schema(response_schema)

    payload = {
        "systemInstruction": {
            "parts": [{"text": system}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": gemini_schema,
        },
    }

    req = request.Request(
        url=url,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            detail = str(exc)
        raise RuntimeError(f"Gemini API error ({exc.code}): {detail}") from exc
    except urlerror.URLError as exc:
        raise RuntimeError(f"Gemini API connection error: {exc}") from exc

    parsed = json.loads(body)
    candidates = parsed.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini response has no candidates")

    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    if not parts:
        raise RuntimeError("Gemini response has no content parts")

    # Structured output currently arrives as JSON text in first part.
    text = parts[0].get("text")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Gemini response part does not contain JSON text")

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.exception("Failed to parse Gemini JSON: %s", text[:500])
        raise RuntimeError("Gemini returned non-JSON text") from exc

from __future__ import annotations

import base64
import json
import time
from urllib import error as urlerror
from urllib import parse, request

from app.infra.ports.llm import LLMPort

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


def _normalize_schema_type(type_value: object) -> tuple[str | None, bool]:
    if isinstance(type_value, str):
        mapped = _TYPE_MAP.get(type_value.lower())
        return mapped, False

    if isinstance(type_value, list):
        types = [item for item in type_value if isinstance(item, str)]
        nullable = any(item.lower() == "null" for item in types)
        non_null = [item for item in types if item.lower() != "null"]
        if not non_null:
            return None, nullable
        mapped = _TYPE_MAP.get(non_null[0].lower())
        return mapped, nullable

    return None, False


def _to_gemini_response_schema(node: object) -> dict:
    if not isinstance(node, dict):
        return {}

    out: dict[str, object] = {}
    mapped_type, nullable = _normalize_schema_type(node.get("type"))
    if mapped_type:
        out["type"] = mapped_type
    if nullable:
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
        out["required"] = [item for item in node["required"] if isinstance(item, str)]

    properties = node.get("properties")
    if isinstance(properties, dict):
        out["properties"] = {
            key: _to_gemini_response_schema(value)
            for key, value in properties.items()
            if isinstance(key, str)
        }

    items = node.get("items")
    if isinstance(items, dict):
        out["items"] = _to_gemini_response_schema(items)
    elif isinstance(items, list) and items and isinstance(items[0], dict):
        out["items"] = _to_gemini_response_schema(items[0])

    return out


class GeminiLLM(LLMPort):
    provider_name = "gemini"

    def __init__(self, *, api_key: str, model_name: str, timeout_seconds: int = 90, max_retries: int = 1):
        self.api_key = api_key
        self.model_name = model_name
        self.timeout_seconds = max(3, int(timeout_seconds))
        self.max_retries = max(0, int(max_retries))

    @staticmethod
    def _is_timeout_error(exc: Exception) -> bool:
        reason = getattr(exc, "reason", None)
        message = f"{exc} {reason or ''}".lower()
        return isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError) or "timed out" in message

    @staticmethod
    def _is_retryable_http(status_code: int) -> bool:
        return status_code in {408, 429, 500, 502, 503, 504}

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: dict,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> dict:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt[:12000]}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": _to_gemini_response_schema(schema),
            },
        }
        return self._request_json(payload=payload, system_prompt=system_prompt, model=model)

    def generate_structured_from_media(
        self,
        *,
        prompt: str,
        schema: dict,
        media_bytes: bytes,
        media_mime_type: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> dict:
        encoded = base64.b64encode(media_bytes).decode("ascii")
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt[:12000]},
                        {
                            "inlineData": {
                                "mimeType": media_mime_type,
                                "data": encoded,
                            }
                        },
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": _to_gemini_response_schema(schema),
            },
        }
        return self._request_json(payload=payload, system_prompt=system_prompt, model=model)

    def _request_json(self, *, payload: dict, system_prompt: str | None, model: str | None) -> dict:
        model_name = model or self.model_name
        url = (
            f"{_GOOGLE_AI_BASE}/models/{parse.quote(model_name)}:generateContent"
            f"?key={parse.quote(self.api_key)}"
        )
        payload = dict(payload)
        payload["systemInstruction"] = {
            "parts": [{"text": (system_prompt or "Return strict JSON only.")[:6000]}],
        }

        req = request.Request(
            url=url,
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        body: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body = resp.read().decode("utf-8")
                    break
            except urlerror.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8")
                except Exception:
                    detail = str(exc)
                if self._is_retryable_http(exc.code) and attempt < self.max_retries:
                    time.sleep(min(6.0, 1.2 * (attempt + 1)))
                    continue
                raise RuntimeError(f"Gemini API error ({exc.code}): {detail}") from exc
            except urlerror.URLError as exc:
                if self._is_timeout_error(exc) and attempt < self.max_retries:
                    time.sleep(min(6.0, 1.2 * (attempt + 1)))
                    continue
                raise RuntimeError(f"Gemini API connection error: {exc}") from exc
            except TimeoutError as exc:
                if attempt < self.max_retries:
                    time.sleep(min(6.0, 1.2 * (attempt + 1)))
                    continue
                raise RuntimeError(
                    f"Gemini API timeout after {self.max_retries + 1} attempts "
                    f"(timeout={self.timeout_seconds}s)."
                ) from exc

        if body is None:
            raise RuntimeError(
                f"Gemini API timeout after {self.max_retries + 1} attempts "
                f"(timeout={self.timeout_seconds}s)."
            )

        parsed = json.loads(body)
        candidates = parsed.get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini response has no candidates")

        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        if not parts:
            raise RuntimeError("Gemini response has no content parts")

        text = parts[0].get("text")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Gemini response part does not contain JSON text")

        data = json.loads(text)
        if not isinstance(data, dict):
            raise RuntimeError("Gemini structured output is not a JSON object")

        data.setdefault("provider", self.provider_name)
        data.setdefault("model", model_name)
        return data

from __future__ import annotations

from typing import Any

from app.infra.ports.llm import LLMPort


class MockLLM(LLMPort):
    def generate_structured(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": "mock",
            "promptPreview": prompt[:80],
            "schemaKeys": sorted(list(schema.keys())),
        }

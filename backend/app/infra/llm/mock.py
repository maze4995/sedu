from __future__ import annotations

from typing import Any

from app.infra.ports.llm import LLMPort


class MockLLM(LLMPort):
    provider_name = "mock"
    model_name = "mock-llm-v2"

    def generate_structured(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": model or self.model_name,
            "promptPreview": prompt[:80],
            "schemaKeys": sorted(list(schema.keys())),
            "systemPromptPreview": (system_prompt or "")[:80],
        }

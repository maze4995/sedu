"""Gemini structured-output call wrapper.

TODO: Implement when google-genai SDK is integrated.

Usage (future):
    from app.gemini.client import call_gemini_structured
    result = call_gemini_structured(
        model_name="gemini-2.0-flash",
        system="...",
        user="...",
        schema_path="question_structure.v1.json",
    )
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def call_gemini_structured(
    *,
    model_name: str,
    system: str,
    user: str,
    schema_path: str,
) -> dict:
    """Call Gemini with structured output constrained to the given JSON schema.

    Args:
        model_name: Gemini model identifier (e.g. "gemini-2.0-flash").
        system: System prompt text.
        user: User prompt text.
        schema_path: Filename of the JSON schema in app/gemini/schemas/.

    Returns:
        Parsed dict conforming to the schema.

    Raises:
        NotImplementedError: Until the google-genai SDK is integrated.
        RuntimeError: If GEMINI_API_KEY is not set.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is required. "
            "Get one at https://aistudio.google.com/apikey"
        )

    schema_file = _SCHEMA_DIR / schema_path
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema not found: {schema_file}")

    with open(schema_file, encoding="utf-8") as f:
        _schema = json.load(f)

    # TODO: Replace stub with actual Gemini API call.
    #
    # Planned implementation with google-genai SDK:
    #
    #   from google import genai
    #   client = genai.Client(api_key=api_key)
    #   response = client.models.generate_content(
    #       model=model_name,
    #       contents=user,
    #       config=genai.types.GenerateContentConfig(
    #           system_instruction=system,
    #           response_mime_type="application/json",
    #           response_schema=_schema,
    #       ),
    #   )
    #   return json.loads(response.text)

    raise NotImplementedError(
        "Gemini API integration is not yet implemented. "
        "Install google-genai and replace this stub."
    )

"""Render Gemini prompt templates with placeholder substitution."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TypedDict

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


class RenderedPrompt(TypedDict):
    system: str
    user: str


@lru_cache(maxsize=8)
def _load_template(name: str) -> str:
    path = _PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _render(template: str, values: dict[str, str]) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def render_question_structure_prompt(input_dict: dict[str, str]) -> RenderedPrompt:
    """Render question_structure system + user prompts."""
    system = _load_template("question_structure.system.txt")
    user = _load_template("question_structure.user.txt")
    return RenderedPrompt(
        system=_render(system, input_dict),
        user=_render(user, input_dict),
    )


def render_segmentation_qc_prompt(input_dict: dict[str, str]) -> RenderedPrompt:
    """Render segmentation_qc system + user prompts."""
    system = _load_template("segmentation_qc.system.txt")
    user = _load_template("segmentation_qc.user.txt")
    return RenderedPrompt(
        system=_render(system, input_dict),
        user=_render(user, input_dict),
    )

"""Crop question regions from page images."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.pipeline.layout import QuestionBBox


def crop_questions_from_page(
    page_image: Image.Image,
    bboxes: list[QuestionBBox],
) -> list[Image.Image]:
    """Crop each bbox region from the page image.

    Returns a list of cropped PIL Images in the same order as *bboxes*.
    """
    crops: list[Image.Image] = []
    for bbox in bboxes:
        region = page_image.crop((bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]))
        crops.append(region)
    return crops


def save_question_image(image: Image.Image, path: str | Path) -> None:
    """Save a cropped question image to disk (PNG)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(p), format="PNG")

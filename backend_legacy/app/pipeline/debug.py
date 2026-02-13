"""Debug visualisation helpers for the extraction pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image
    from app.pipeline.layout import QuestionBBox

# Colour cycle for bboxes (BGR for OpenCV).
_COLOURS = [
    (0, 200, 0),     # green
    (200, 0, 0),     # blue
    (0, 0, 200),     # red
    (200, 200, 0),   # cyan
    (0, 200, 200),   # yellow
    (200, 0, 200),   # magenta
]


def draw_bboxes(
    page_image: Image.Image,
    bboxes: list[QuestionBBox],
    output_path: str | Path,
) -> None:
    """Draw labelled rectangles on a page image and save to *output_path*.

    Each question bbox gets a distinct colour and a number label overlay.
    """
    import cv2
    import numpy as np

    arr = cv2.cvtColor(np.array(page_image), cv2.COLOR_RGB2BGR)

    for i, bbox in enumerate(bboxes):
        colour = _COLOURS[i % len(_COLOURS)]
        pt1 = (bbox["x1"], bbox["y1"])
        pt2 = (bbox["x2"], bbox["y2"])

        cv2.rectangle(arr, pt1, pt2, colour, 2)

        label = bbox.get("number_label", str(i + 1))
        cv2.putText(
            arr,
            f"Q{label}",
            (bbox["x1"] + 4, bbox["y1"] + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            colour,
            2,
        )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), arr)

"""Question number detection and bbox construction.

Deterministic, regex-based approach for Korean exam pages.
"""

from __future__ import annotations

import re
from typing import TypedDict


class BBox(TypedDict):
    x1: int
    y1: int
    x2: int
    y2: int


class OcrToken(TypedDict):
    text: str
    bbox: BBox
    conf: float | None


class AnchorToken(TypedDict):
    text: str
    bbox: BBox
    conf: float | None
    number_label: str


class QuestionBBox(TypedDict):
    x1: int
    y1: int
    x2: int
    y2: int
    number_label: str


# ── Patterns ────────────────────────────────────────────────────────

# Matches:  1.  2.  3)  (4)  [5]  6  01.  12)
# Captures the bare number for use as label.
_QUESTION_NUMBER_RE = re.compile(
    r"^"
    r"(?:"
    r"\((\d{1,2})\)"       # (4)
    r"|\[(\d{1,2})\]"     # [5]
    r"|(\d{1,2})[.\)]"    # 1.  2)
    r"|(\d{1,2})"         # bare 6
    r")"
    r"$"
)


def is_question_number(text: str) -> bool:
    """Return True if *text* looks like a question number token."""
    return _QUESTION_NUMBER_RE.match(text.strip()) is not None


def _extract_number_label(text: str) -> str:
    """Extract the bare numeric label from a question-number token."""
    m = _QUESTION_NUMBER_RE.match(text.strip())
    if m is None:
        return text.strip()
    # Return the first non-None capture group.
    for g in m.groups():
        if g is not None:
            return g
    return text.strip()


# ── Detection ───────────────────────────────────────────────────────


def detect_question_anchors(ocr_tokens: list[OcrToken]) -> list[AnchorToken]:
    """Filter OCR tokens that look like question numbers, sorted by y1.

    Returns anchor tokens with an added ``number_label`` field.
    """
    return detect_question_anchors_with_page(ocr_tokens, page_height=None)


_TOP_NOISE_RATIO = 0.04
_BOTTOM_NOISE_RATIO = 0.04
_MIN_MARGIN_PX = 30


def _is_in_body_region(*, y1: int, y2: int, page_height: int | None) -> bool:
    if not isinstance(page_height, int) or page_height <= 0:
        return True

    margin = max(_MIN_MARGIN_PX, int(page_height * _TOP_NOISE_RATIO))
    top_limit = margin
    bottom_limit = page_height - max(_MIN_MARGIN_PX, int(page_height * _BOTTOM_NOISE_RATIO))
    return y1 >= top_limit and y2 <= bottom_limit


def detect_question_anchors_with_page(
    ocr_tokens: list[OcrToken],
    *,
    page_height: int | None,
) -> list[AnchorToken]:
    """Detect anchors while filtering header/footer/page-number noise tokens."""
    anchors: list[AnchorToken] = []
    for tok in ocr_tokens:
        text = tok["text"].strip()
        if not text:
            continue
        bbox = tok["bbox"]
        if not _is_in_body_region(
            y1=int(bbox["y1"]),
            y2=int(bbox["y2"]),
            page_height=page_height,
        ):
            continue
        if is_question_number(text):
            anchors.append(
                AnchorToken(
                    text=text,
                    bbox=bbox,
                    conf=tok.get("conf"),
                    number_label=_extract_number_label(text),
                )
            )

    # Sort top-to-bottom by y1, then left-to-right by x1 for ties.
    anchors.sort(key=lambda a: (a["bbox"]["y1"], a["bbox"]["x1"]))

    # Deduplicate: if two consecutive anchors have the same number_label
    # AND are very close vertically, keep only the first.
    deduped: list[AnchorToken] = []
    for anchor in anchors:
        if deduped:
            prev = deduped[-1]
            same_label = prev["number_label"] == anchor["number_label"]
            close_y = abs(anchor["bbox"]["y1"] - prev["bbox"]["y1"]) < 20
            if same_label and close_y:
                continue
        deduped.append(anchor)

    return deduped


# ── Bbox construction ───────────────────────────────────────────────

_Y_MARGIN_TOP = 8   # pixels above the anchor
_Y_MARGIN_BOT = 4   # pixels gap before next question


def build_question_bboxes(
    anchors: list[AnchorToken],
    page_width: int,
    page_height: int,
) -> list[QuestionBBox]:
    """Build full-width bounding boxes from anchor tokens.

    Each question spans from its anchor's y1 (minus margin) down to the
    next anchor's y1 (or page bottom for the last question).
    """
    if not anchors:
        return []

    bboxes: list[QuestionBBox] = []
    for i, anchor in enumerate(anchors):
        top = max(0, anchor["bbox"]["y1"] - _Y_MARGIN_TOP)

        if i + 1 < len(anchors):
            bottom = max(top, anchors[i + 1]["bbox"]["y1"] - _Y_MARGIN_BOT)
        else:
            bottom = page_height

        bboxes.append(
            QuestionBBox(
                x1=0,
                y1=top,
                x2=page_width,
                y2=bottom,
                number_label=anchor["number_label"],
            )
        )

    return bboxes

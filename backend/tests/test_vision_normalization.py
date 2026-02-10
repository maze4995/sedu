"""Tests for Vision OCR response normalization and token flattening."""

from types import SimpleNamespace

from app.ocr.vision_client import normalize_response
from app.pipeline.ocr_step import _flatten_tokens


# ── Helpers to build mock Vision response objects ───────────────────


def _vertex(x: int, y: int) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y)


def _symbol(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def _word(
    symbols: list[str],
    vertices: list[tuple[int, int]],
    confidence: float | None = None,
) -> SimpleNamespace:
    v = [_vertex(x, y) for x, y in vertices]
    w = SimpleNamespace(
        symbols=[_symbol(s) for s in symbols],
        bounding_box=SimpleNamespace(vertices=v),
    )
    if confidence is not None:
        w.confidence = confidence
    else:
        w.confidence = None
    return w


def _paragraph(words: list) -> SimpleNamespace:
    return SimpleNamespace(words=words)


def _block(paragraphs: list) -> SimpleNamespace:
    return SimpleNamespace(paragraphs=paragraphs)


def _page(blocks: list) -> SimpleNamespace:
    return SimpleNamespace(blocks=blocks)


def _response(text: str, pages: list) -> SimpleNamespace:
    return SimpleNamespace(
        full_text_annotation=SimpleNamespace(text=text, pages=pages),
        error=None,
    )


def _empty_response() -> SimpleNamespace:
    return SimpleNamespace(
        full_text_annotation=SimpleNamespace(text="", pages=[]),
        error=None,
    )


# ── normalize_response tests ───────────────────────────────────────


class TestNormalizeResponse:
    def test_empty_response(self):
        result = normalize_response(_empty_response())
        assert result["full_text"] == ""
        assert result["pages"] == []
        assert result["avg_confidence"] is None

    def test_single_word(self):
        word = _word(
            ["다", "음"],
            [(10, 20), (50, 20), (50, 40), (10, 40)],
            confidence=0.95,
        )
        resp = _response("다음", [_page([_block([_paragraph([word])])])])
        result = normalize_response(resp)

        assert result["full_text"] == "다음"
        assert result["avg_confidence"] == 0.95

        words = result["pages"][0]["blocks"][0]["paragraphs"][0]["words"]
        assert len(words) == 1
        assert words[0]["text"] == "다음"
        assert words[0]["confidence"] == 0.95
        assert words[0]["bbox"] == {"x1": 10, "y1": 20, "x2": 50, "y2": 40}

    def test_multiple_words_avg_confidence(self):
        w1 = _word(["가"], [(0, 0), (10, 0), (10, 10), (0, 10)], confidence=0.90)
        w2 = _word(["나"], [(20, 0), (30, 0), (30, 10), (20, 10)], confidence=0.80)
        w3 = _word(["다"], [(40, 0), (50, 0), (50, 10), (40, 10)], confidence=0.70)

        resp = _response("가 나 다", [_page([_block([_paragraph([w1, w2, w3])])])])
        result = normalize_response(resp)

        expected_avg = round((0.90 + 0.80 + 0.70) / 3, 4)
        assert result["avg_confidence"] == expected_avg

    def test_null_confidence_word(self):
        w1 = _word(["가"], [(0, 0), (10, 0), (10, 10), (0, 10)], confidence=0.90)
        w2 = _word(["나"], [(20, 0), (30, 0), (30, 10), (20, 10)], confidence=None)

        resp = _response("가 나", [_page([_block([_paragraph([w1, w2])])])])
        result = normalize_response(resp)

        # Only w1 has confidence, so avg = 0.90
        assert result["avg_confidence"] == 0.90

        words = result["pages"][0]["blocks"][0]["paragraphs"][0]["words"]
        assert words[1]["confidence"] is None

    def test_bbox_min_max(self):
        # Rotated vertices where min/max aren't at index 0 and 2.
        word = _word(
            ["A"],
            [(30, 5), (55, 10), (50, 35), (25, 30)],
            confidence=0.99,
        )
        resp = _response("A", [_page([_block([_paragraph([word])])])])
        result = normalize_response(resp)

        bbox = result["pages"][0]["blocks"][0]["paragraphs"][0]["words"][0]["bbox"]
        assert bbox == {"x1": 25, "y1": 5, "x2": 55, "y2": 35}

    def test_multiple_pages(self):
        w1 = _word(["P1"], [(0, 0), (10, 0), (10, 10), (0, 10)], confidence=0.85)
        w2 = _word(["P2"], [(0, 0), (10, 0), (10, 10), (0, 10)], confidence=0.95)

        resp = _response(
            "P1 P2",
            [
                _page([_block([_paragraph([w1])])]),
                _page([_block([_paragraph([w2])])]),
            ],
        )
        result = normalize_response(resp)

        assert len(result["pages"]) == 2
        assert result["avg_confidence"] == round((0.85 + 0.95) / 2, 4)


# ── _flatten_tokens tests ──────────────────────────────────────────


class TestFlattenTokens:
    def test_flattens_hierarchy(self):
        pages = [
            {
                "blocks": [
                    {
                        "paragraphs": [
                            {
                                "words": [
                                    {"text": "가", "bbox": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}, "confidence": 0.9},
                                    {"text": "나", "bbox": {"x1": 15, "y1": 0, "x2": 25, "y2": 10}, "confidence": 0.8},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        tokens = _flatten_tokens(pages)
        assert len(tokens) == 2
        assert tokens[0] == {"text": "가", "bbox": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}, "conf": 0.9}
        assert tokens[1] == {"text": "나", "bbox": {"x1": 15, "y1": 0, "x2": 25, "y2": 10}, "conf": 0.8}

    def test_empty_pages(self):
        assert _flatten_tokens([]) == []

    def test_multiple_blocks_and_paragraphs(self):
        pages = [
            {
                "blocks": [
                    {
                        "paragraphs": [
                            {"words": [{"text": "A", "bbox": {"x1": 0, "y1": 0, "x2": 5, "y2": 5}, "confidence": 0.9}]},
                            {"words": [{"text": "B", "bbox": {"x1": 10, "y1": 0, "x2": 15, "y2": 5}, "confidence": 0.8}]},
                        ]
                    },
                    {
                        "paragraphs": [
                            {"words": [{"text": "C", "bbox": {"x1": 0, "y1": 20, "x2": 5, "y2": 25}, "confidence": None}]},
                        ]
                    },
                ]
            }
        ]
        tokens = _flatten_tokens(pages)
        assert len(tokens) == 3
        assert tokens[2]["text"] == "C"
        assert tokens[2]["conf"] is None

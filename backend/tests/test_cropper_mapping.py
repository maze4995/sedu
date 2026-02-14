from app.workers.extraction.cropper import QuestionCropper


class DummyStorage:
    def save_bytes(self, key: str, data: bytes, content_type: str | None) -> str:
        return f"/uploads/{key}"

    def build_url(self, key: str) -> str:
        return f"/uploads/{key}"


class DummyVisionOCR:
    provider_name = "google_vision"

    def extract(self, image_bytes: bytes):
        return {
            "text": "1 ... 3 ... 4 ...",
            "confidence": 0.95,
            "tokens": [
                {"text": "1", "bbox": {"x1": 10, "y1": 100, "x2": 20, "y2": 120}, "conf": 0.9},
                {"text": "2", "bbox": {"x1": 420, "y1": 220, "x2": 430, "y2": 240}, "conf": 0.9},
                {"text": "3", "bbox": {"x1": 12, "y1": 380, "x2": 22, "y2": 398}, "conf": 0.9},
                {"text": "4", "bbox": {"x1": 12, "y1": 540, "x2": 22, "y2": 558}, "conf": 0.9},
            ],
        }


def test_pick_starts_prefers_matching_question_labels():
    detected = [
        (100, 1),
        (250, 2),
        (400, 3),
        (550, 4),
        (700, 5),
    ]
    labels = ["1", "3", "4", "5"]
    starts = QuestionCropper._pick_starts_for_questions(
        height=1000,
        question_labels=labels,
        detected_starts=detected,
    )
    assert starts == [100, 400, 550, 700]


def test_normalize_ranges_extends_when_starts_are_fewer_than_questions():
    ranges = QuestionCropper._normalize_ranges(height=1000, count=4, starts=[100, 300])
    assert len(ranges) == 4
    assert ranges[0][0] <= 100
    assert ranges[-1][1] <= 1000


def test_starts_from_tokens_uses_left_margin_filter():
    tokens = [
        {"text": "1", "bbox": {"x1": 12, "y1": 100, "x2": 24, "y2": 118}},
        {"text": "2", "bbox": {"x1": 500, "y1": 210, "x2": 512, "y2": 228}},
        {"text": "3", "bbox": {"x1": 14, "y1": 350, "x2": 26, "y2": 368}},
    ]
    starts = QuestionCropper._starts_from_tokens(tokens, width=1200)
    assert starts == [(100, 1), (350, 3)]


def test_detect_question_starts_prefers_secondary_ocr_tokens():
    from PIL import Image

    image = Image.new("RGB", (1200, 800), "white")
    cropper = QuestionCropper(storage=DummyStorage(), secondary_ocr=DummyVisionOCR())
    starts = cropper._detect_question_starts(image)
    assert starts == [(100, 1), (380, 3), (540, 4)]


def test_label_sequence_reliability_requires_mostly_contiguous_numbers():
    assert QuestionCropper._is_label_sequence_reliable(["1", "2", "3", "4"]) is True
    assert QuestionCropper._is_label_sequence_reliable(["1", "3", "5"]) is False
    assert QuestionCropper._is_label_sequence_reliable([None, "1", None]) is False


def test_create_and_store_falls_back_to_order_when_labels_unreliable(monkeypatch):
    class DummyCanvas:
        width = 1000
        height = 1000

        def crop(self, _box):
            return self

    captured: dict[str, list[int] | None] = {"starts": None}
    cropper = QuestionCropper(storage=DummyStorage(), secondary_ocr=DummyVisionOCR())

    monkeypatch.setattr(cropper, "_render_canvas", lambda **_kwargs: DummyCanvas())
    monkeypatch.setattr(cropper, "_detect_question_starts", lambda _image: [(100, 1), (320, 2), (640, 3)])
    monkeypatch.setattr(cropper, "_encode_png", lambda _image: b"png")

    def fake_normalize_ranges(*, height: int, count: int, starts: list[int] | None = None):
        captured["starts"] = starts
        return [(0, 10) for _ in range(count)]

    monkeypatch.setattr(QuestionCropper, "_normalize_ranges", staticmethod(fake_normalize_ranges))

    cropper.create_and_store(
        set_id="set_1",
        payload=b"pdf",
        content_type="application/pdf",
        filename="a.pdf",
        question_count=3,
        question_labels=["1", "3", "5"],
    )
    assert captured["starts"] == [100, 320, 640]


def test_ranges_from_hints_builds_crop_ranges():
    ranges = QuestionCropper._ranges_from_hints(
        height=1000,
        count=2,
        hints=[
            {"topRatio": 0.1, "bottomRatio": 0.45},
            {"topRatio": 0.5, "bottomRatio": 0.95},
        ],
    )
    assert ranges == [(100, 450), (500, 1000)]


def test_ranges_from_page_hints_supports_page_index_and_partial_fallback():
    planned = QuestionCropper._ranges_from_page_hints(
        page_heights=[1000, 800],
        page_widths=[900, 900],
        question_count=3,
        hints=[
            {"pageIndex": 1, "topRatio": 0.1, "bottomRatio": 0.4},
            {"pageIndex": 1, "topRatio": None, "bottomRatio": None},
            {"pageIndex": 2, "topRatio": 0.2, "bottomRatio": 0.8},
        ],
    )
    assert planned is not None
    assert len(planned) == 3
    # (page_zero, y1, y2, x1, x2, source)
    assert planned[0][0] == 0
    assert planned[1][0] == 0
    assert planned[2][0] == 1
    assert planned[0][5] == "gemini"
    assert planned[1][5] == "fallback"
    assert planned[2][5] == "gemini"
    # No X hints -> full width
    assert planned[0][3] == 0      # x1
    assert planned[0][4] == 900    # x2


def test_create_and_store_with_trace_uses_page_hints_first(monkeypatch):
    class DummyPage:
        width = 900
        height = 1000

        def crop(self, _box):
            return self

    cropper = QuestionCropper(storage=DummyStorage(), secondary_ocr=DummyVisionOCR())
    monkeypatch.setattr(cropper, "_render_pages", lambda **_kwargs: [DummyPage(), DummyPage()])
    monkeypatch.setattr(cropper, "_encode_png", lambda _image: b"png")

    traces = cropper.create_and_store_with_trace(
        set_id="set_1",
        payload=b"pdf",
        content_type="application/pdf",
        filename="a.pdf",
        question_count=2,
        question_crop_hints=[
            {"pageIndex": 1, "topRatio": 0.1, "bottomRatio": 0.5},
            {"pageIndex": 2, "topRatio": 0.2, "bottomRatio": 0.8},
        ],
    )
    assert len(traces) == 2
    assert traces[0]["cropSource"] == "gemini"
    assert traces[1]["cropSource"] == "gemini"
    assert traces[0]["pageIndex"] == 1
    assert traces[1]["pageIndex"] == 2


def test_ranges_from_page_hints_two_column_layout():
    """Two-column hints produce separate X ranges for left/right columns."""
    planned = QuestionCropper._ranges_from_page_hints(
        page_heights=[1000],
        page_widths=[800],
        question_count=4,
        hints=[
            {"pageIndex": 1, "topRatio": 0.05, "bottomRatio": 0.45, "leftRatio": 0.0, "rightRatio": 0.5},
            {"pageIndex": 1, "topRatio": 0.50, "bottomRatio": 0.95, "leftRatio": 0.0, "rightRatio": 0.5},
            {"pageIndex": 1, "topRatio": 0.05, "bottomRatio": 0.45, "leftRatio": 0.5, "rightRatio": 1.0},
            {"pageIndex": 1, "topRatio": 0.50, "bottomRatio": 0.95, "leftRatio": 0.5, "rightRatio": 1.0},
        ],
    )
    assert planned is not None
    assert len(planned) == 4
    # All on page 0
    assert all(p[0] == 0 for p in planned)
    # Left column: x1=0, x2=400
    assert planned[0][3] == 0
    assert planned[0][4] == 400
    assert planned[1][3] == 0
    assert planned[1][4] == 400
    # Right column: x1=400, x2=800
    assert planned[2][3] == 400
    assert planned[2][4] == 800
    assert planned[3][3] == 400
    assert planned[3][4] == 800
    # All from gemini
    assert all(p[5] == "gemini" for p in planned)


def test_ranges_from_page_hints_no_x_hints_uses_full_width():
    """Without leftRatio/rightRatio, x spans full page width."""
    planned = QuestionCropper._ranges_from_page_hints(
        page_heights=[1000],
        page_widths=[800],
        question_count=1,
        hints=[
            {"pageIndex": 1, "topRatio": 0.1, "bottomRatio": 0.9},
        ],
    )
    assert planned is not None
    assert planned[0][3] == 0     # x1 = full width
    assert planned[0][4] == 800   # x2 = full width


def test_ranges_from_page_hints_enforces_minimum_crop_height():
    """Crops smaller than 60px get expanded."""
    planned = QuestionCropper._ranges_from_page_hints(
        page_heights=[1000],
        page_widths=[800],
        question_count=1,
        hints=[
            {"pageIndex": 1, "topRatio": 0.5, "bottomRatio": 0.52},
        ],
    )
    assert planned is not None
    y1, y2 = planned[0][1], planned[0][2]
    assert y2 - y1 >= 60


def test_postprocess_crop_hints_expands_tiny_crops():
    from app.workers.extraction.pipeline import DocumentExtractionPipeline, ExtractedQuestion

    questions = [
        ExtractedQuestion(
            order_index=1,
            number_label="1",
            text="Q1",
            confidence=0.9,
            metadata={"cropHint": {"pageIndex": 1, "topRatio": 0.5, "bottomRatio": 0.52}},
        ),
    ]
    result = DocumentExtractionPipeline._postprocess_crop_hints(questions)
    hint = result[0].metadata["cropHint"]
    assert hint["bottomRatio"] - hint["topRatio"] >= 0.05


def test_postprocess_crop_hints_fixes_overlap():
    from app.workers.extraction.pipeline import DocumentExtractionPipeline, ExtractedQuestion

    questions = [
        ExtractedQuestion(
            order_index=1,
            number_label="1",
            text="Q1",
            confidence=0.9,
            metadata={"cropHint": {"pageIndex": 1, "topRatio": 0.0, "bottomRatio": 0.6}},
        ),
        ExtractedQuestion(
            order_index=2,
            number_label="2",
            text="Q2",
            confidence=0.9,
            metadata={"cropHint": {"pageIndex": 1, "topRatio": 0.4, "bottomRatio": 0.9}},
        ),
    ]
    result = DocumentExtractionPipeline._postprocess_crop_hints(questions)
    h0 = result[0].metadata["cropHint"]
    h1 = result[1].metadata["cropHint"]
    # No overlap: q1 bottom <= q2 top
    assert h0["bottomRatio"] <= h1["topRatio"]


def test_postprocess_crop_hints_orders_left_before_right():
    from app.workers.extraction.pipeline import DocumentExtractionPipeline, ExtractedQuestion

    questions = [
        ExtractedQuestion(
            order_index=1,
            number_label="3",
            text="Q3 right",
            confidence=0.9,
            metadata={"cropHint": {"pageIndex": 1, "topRatio": 0.0, "bottomRatio": 0.5, "leftRatio": 0.5, "rightRatio": 1.0}},
        ),
        ExtractedQuestion(
            order_index=2,
            number_label="1",
            text="Q1 left",
            confidence=0.9,
            metadata={"cropHint": {"pageIndex": 1, "topRatio": 0.0, "bottomRatio": 0.5, "leftRatio": 0.0, "rightRatio": 0.5}},
        ),
    ]
    result = DocumentExtractionPipeline._postprocess_crop_hints(questions)
    # Left column should come first
    assert result[0].text == "Q1 left"
    assert result[1].text == "Q3 right"
    # order_index re-assigned
    assert result[0].order_index == 1
    assert result[1].order_index == 2

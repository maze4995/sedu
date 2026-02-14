from __future__ import annotations

import pytest
from typing import Any

from app.workers.extraction import DocumentExtractionPipeline


class StubOCR:
    def __init__(self, text: str, confidence: float = 0.8):
        self._text = text
        self._confidence = confidence

    def extract(self, image_bytes: bytes) -> dict[str, Any]:
        return {
            "text": self._text,
            "confidence": self._confidence,
            "tokens": [],
        }


class StubLLM:
    provider_name = "gemini"
    model_name = "gemini-test"

    def generate_structured(self, *, prompt: str, schema: dict[str, Any], system_prompt: str | None = None, model: str | None = None):
        return {
            "questions": [
                {
                    "orderIndex": 1,
                    "numberLabel": "1",
                    "text": "1. LLM이 보정한 문제 본문",
                    "confidence": 0.93,
                    "subject": "science",
                    "unit": "화학",
                    "difficulty": "middle",
                    "questionType": "multiple_choice",
                    "answerFormat": "single_choice",
                }
            ]
        }

    def generate_structured_from_media(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        media_bytes: bytes,
        media_mime_type: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ):
        return {
            "questions": [
                {
                    "orderIndex": 1,
                    "numberLabel": "1",
                    "text": "1. Gemini가 문서를 직접 읽은 문제",
                    "confidence": 0.95,
                    "subject": "science",
                    "unit": "화학",
                    "difficulty": "middle",
                    "questionType": "multiple_choice",
                    "answerFormat": "single_choice",
                    "cropTopRatio": 0.1,
                    "cropBottomRatio": 0.45,
                }
            ]
        }


class StubVisionOCR:
    provider_name = "google_vision"

    def extract(self, image_bytes: bytes) -> dict[str, Any]:
        return {
            "text": "1. Vision OCR first pass text",
            "confidence": 0.89,
            "tokens": [],
        }


class StubLLMEmptyStructuredThenRaw:
    provider_name = "gemini"
    model_name = "gemini-test"

    def __init__(self):
        self.call_count = 0

    def generate_structured_from_media(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        media_bytes: bytes,
        media_mime_type: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ):
        self.call_count += 1
        if self.call_count == 1:
            return {"questions": []}
        return {"rawText": "1. 원문 추출\n2. 두번째 문제"}


class StubLLMStructuredTimeoutThenRaw:
    provider_name = "gemini"
    model_name = "gemini-test"

    def __init__(self):
        self.call_count = 0

    def generate_structured_from_media(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        media_bytes: bytes,
        media_mime_type: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ):
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("The read operation timed out")
        return {"rawText": "1. 타임아웃 후 원문 추출"}


class StubLLMAlwaysFails:
    provider_name = "gemini"
    model_name = "gemini-test"

    def generate_structured_from_media(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        media_bytes: bytes,
        media_mime_type: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ):
        raise RuntimeError("timeout")


class StubLLMPaged:
    provider_name = "gemini"
    model_name = "gemini-test"

    def __init__(self):
        self.call_count = 0

    def generate_structured_from_media(
        self,
        *,
        prompt: str,
        schema: dict[str, Any],
        media_bytes: bytes,
        media_mime_type: str,
        system_prompt: str | None = None,
        model: str | None = None,
    ):
        self.call_count += 1
        page = self.call_count
        return {
            "questions": [
                {
                    "orderIndex": 1,
                    "numberLabel": str(page),
                    "text": f"{page}. page {page} question",
                    "confidence": 0.94,
                    "subject": "science",
                    "unit": "chemistry",
                    "difficulty": "middle",
                    "questionType": "multiple_choice",
                    "answerFormat": "single_choice",
                    "cropTopRatio": 0.1,
                    "cropBottomRatio": 0.9,
                }
            ]
        }


def test_pipeline_splits_numbered_questions_from_fallback_ocr():
    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubOCR(
            text=(
                "1. 다음 중 옳은 것은?\n"
                "① 보기 A\n"
                "② 보기 B\n\n"
                "2) 물질 변화에 대한 설명으로 옳은 것은?\n"
                "1) 선택지1\n"
                "2) 선택지2"
            ),
            confidence=0.86,
        )
    )

    result = pipeline.extract(
        payload=b"\xff\xfe\xfd",
        content_type="application/octet-stream",
        filename="sample.bin",
    )

    assert result.engine == "ocr_fallback"
    assert len(result.questions) == 2
    assert result.questions[0].number_label == "1"
    assert "다음 중 옳은 것은" in result.questions[0].text
    assert result.questions[1].number_label == "2"
    assert result.questions[1].order_index == 2
    assert result.questions[0].metadata["engine"] == "ocr_fallback"


def test_pipeline_uses_utf8_decode_before_fallback():
    pipeline = DocumentExtractionPipeline(ocr_fallback=StubOCR(text="fallback", confidence=0.5))
    raw = "1. 첫 문제\n2. 둘째 문제".encode("utf-8")

    result = pipeline.extract(
        payload=raw,
        content_type="text/plain",
        filename="inline.txt",
    )

    assert result.engine == "utf8_decode"
    assert len(result.questions) == 2


def test_pipeline_rewrites_mock_fallback_text_for_user():
    pipeline = DocumentExtractionPipeline(ocr_fallback=StubOCR(text="[mock] OCR text", confidence=0.91))

    result = pipeline.extract(
        payload=b"\x89PNG\r\n",
        content_type="image/png",
        filename="sample.png",
    )

    assert result.engine == "ocr_fallback"
    assert len(result.questions) == 1
    assert "[mock]" not in result.questions[0].text
    assert "Tesseract" in result.questions[0].text


def test_pipeline_uses_llm_refinement_when_available():
    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubOCR(text="1. 깨진 OCR 텍스트", confidence=0.81),
        llm=StubLLM(),
        llm_enabled=True,
    )
    result = pipeline.extract(
        payload=b"\x00\x01",
        content_type="application/octet-stream",
        filename="sample.bin",
    )

    assert result.engine.endswith("+llm")
    assert len(result.questions) == 1
    assert "LLM이 보정한 문제 본문" in result.questions[0].text
    assert result.questions[0].metadata["llmRefined"] is True
    assert result.questions[0].metadata["subject"] == "science"


def test_pipeline_prefers_secondary_vision_ocr_for_image():
    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubVisionOCR(),
        llm_enabled=False,
    )
    result = pipeline.extract(
        payload=b"\x89PNG\r\n\x00\x00",
        content_type="image/png",
        filename="sample.png",
    )

    assert result.engine == "google_vision"
    assert len(result.questions) == 1
    assert "Vision OCR first pass text" in result.questions[0].text


def test_pdf_fallback_engine_name_reflects_secondary_ocr():
    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubVisionOCR(),
        llm_enabled=False,
    )
    import io

    import fitz  # type: ignore
    from PIL import Image

    image = Image.new("RGB", (800, 240), "white")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")

    pdf = fitz.open()
    page = pdf.new_page(width=900, height=600)
    page.insert_image(fitz.Rect(20, 20, 880, 560), stream=image_bytes.getvalue())
    payload = pdf.tobytes()
    pdf.close()

    result = pipeline.extract(
        payload=payload,
        content_type="application/pdf",
        filename="scan.pdf",
    )
    assert result.engine == "google_vision_pdf"


def test_pipeline_uses_gemini_full_mode_for_image_without_ocr():
    import io

    from PIL import Image

    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubOCR(text="fallback", confidence=0.5),
        llm=StubLLM(),
        llm_enabled=True,
        extraction_mode="gemini_full",
    )
    image = Image.new("RGB", (400, 200), "white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    result = pipeline.extract(
        payload=buf.getvalue(),
        content_type="image/png",
        filename="sample.png",
    )

    assert result.engine == "gemini_vision"
    assert len(result.questions) == 1
    assert "Gemini가 문서를 직접 읽은 문제" in result.questions[0].text
    assert result.questions[0].metadata["cropHint"]["topRatio"] == 0.1


def test_pipeline_gemini_full_falls_back_to_gemini_raw_text_when_structured_empty():
    import io

    from PIL import Image

    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubOCR(text="fallback", confidence=0.5),
        llm=StubLLMEmptyStructuredThenRaw(),
        llm_enabled=True,
        extraction_mode="gemini_full",
    )
    image = Image.new("RGB", (400, 200), "white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    result = pipeline.extract(
        payload=buf.getvalue(),
        content_type="image/png",
        filename="sample.png",
    )

    assert result.engine == "gemini_vision_text"
    assert len(result.questions) == 2
    assert result.questions[0].metadata["engine"] == "gemini_vision_text"


def test_pipeline_gemini_full_retries_with_raw_text_when_structured_throws():
    import io

    from PIL import Image

    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubOCR(text="fallback", confidence=0.5),
        llm=StubLLMStructuredTimeoutThenRaw(),
        llm_enabled=True,
        extraction_mode="gemini_full",
    )
    image = Image.new("RGB", (400, 200), "white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    result = pipeline.extract(
        payload=buf.getvalue(),
        content_type="image/png",
        filename="sample.png",
    )

    assert result.engine == "gemini_vision_text"
    assert len(result.questions) == 1
    assert result.questions[0].metadata["engine"] == "gemini_vision_text"


def test_pipeline_gemini_full_raises_when_all_multimodal_attempts_fail():
    import io

    from PIL import Image

    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubOCR(text="fallback", confidence=0.5),
        llm=StubLLMAlwaysFails(),
        llm_enabled=True,
        extraction_mode="gemini_full",
    )
    image = Image.new("RGB", (400, 200), "white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")

    with pytest.raises(RuntimeError):
        pipeline.extract(
            payload=buf.getvalue(),
            content_type="image/png",
            filename="sample.png",
        )


def test_pipeline_gemini_full_processes_pdf_page_by_page():
    import io

    import fitz  # type: ignore
    from PIL import Image, ImageDraw

    pipeline = DocumentExtractionPipeline(
        ocr_fallback=StubOCR(text="fallback", confidence=0.5),
        llm=StubLLMPaged(),
        llm_enabled=True,
        extraction_mode="gemini_full",
    )

    def _page_image(text: str) -> bytes:
        image = Image.new("RGB", (900, 600), "white")
        draw = ImageDraw.Draw(image)
        draw.text((40, 40), text, fill="black")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    pdf = fitz.open()
    page1 = pdf.new_page(width=900, height=600)
    page1.insert_image(fitz.Rect(20, 20, 880, 580), stream=_page_image("p1"))
    page2 = pdf.new_page(width=900, height=600)
    page2.insert_image(fitz.Rect(20, 20, 880, 580), stream=_page_image("p2"))
    payload = pdf.tobytes()
    pdf.close()

    result = pipeline.extract(
        payload=payload,
        content_type="application/pdf",
        filename="sample.pdf",
    )

    assert result.engine == "gemini_vision_pages"
    assert len(result.questions) == 2
    assert result.questions[0].order_index == 1
    assert result.questions[1].order_index == 2
    assert result.questions[0].metadata["pageIndex"] == 1
    assert result.questions[1].metadata["pageIndex"] == 2

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.infra.ports.llm import LLMPort
from app.infra.ports.ocr import OCRPort
from app.workers.extraction.cropper import QuestionCropper

_QUESTION_PATTERN = re.compile(r"(?m)^\s*(\d{1,3})\s*(?:[.)]|번)\s+")
_CHOICE_PATTERN = re.compile(r"(?m)^\s*(?:[①-⑤]|[ㄱ-ㅎ]|[A-Ea-e]|[1-5])(?:[.)]|\s)\s*(.+)$")
_MAX_GEMINI_MEDIA_BYTES = 3_500_000
_LLM_REFINEMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["orderIndex", "text"],
                "properties": {
                    "orderIndex": {"type": "integer"},
                    "numberLabel": {"type": "string"},
                    "text": {"type": "string"},
                    "confidence": {"type": "number"},
                    "subject": {"type": "string"},
                    "unit": {"type": "string"},
                    "difficulty": {"type": "string"},
                    "questionType": {"type": "string"},
                    "answerFormat": {"type": "string"},
                },
            },
        }
    },
}
_LLM_MEDIA_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["orderIndex", "text"],
                "properties": {
                    "orderIndex": {"type": "integer"},
                    "numberLabel": {"type": "string"},
                    "text": {"type": "string"},
                    "confidence": {"type": "number"},
                    "subject": {"type": "string"},
                    "unit": {"type": "string"},
                    "difficulty": {"type": "string"},
                    "questionType": {"type": "string"},
                    "answerFormat": {"type": "string"},
                    "cropTopRatio": {"type": ["number", "null"]},
                    "cropBottomRatio": {"type": ["number", "null"]},
                    "cropLeftRatio": {"type": ["number", "null"]},
                    "cropRightRatio": {"type": ["number", "null"]},
                },
            },
        }
    },
}
_LLM_MEDIA_RAW_TEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["rawText"],
    "properties": {
        "rawText": {"type": "string"},
    },
}


@dataclass
class ExtractedQuestion:
    order_index: int
    number_label: str | None
    text: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    questions: list[ExtractedQuestion]
    engine: str
    average_confidence: float
    raw_text: str
    source_type: str


class DocumentExtractionPipeline:
    """Best-effort extraction with real engines and safe fallbacks."""

    def __init__(
        self,
        *,
        ocr_fallback: OCRPort,
        ocr_lang: str = "kor+eng",
        llm: LLMPort | None = None,
        llm_enabled: bool = True,
        llm_model: str | None = None,
        extraction_mode: str = "hybrid",
    ):
        self.ocr_fallback = ocr_fallback
        self.ocr_lang = ocr_lang.strip() if ocr_lang and ocr_lang.strip() else "kor+eng"
        self.llm = llm
        self.llm_enabled = llm_enabled
        self.llm_model = llm_model
        self.extraction_mode = extraction_mode.strip().lower() if extraction_mode else "hybrid"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()

    @staticmethod
    def _split_questions(raw_text: str) -> list[tuple[str | None, str]]:
        text = DocumentExtractionPipeline._normalize_text(raw_text)
        if not text:
            return []

        candidates = list(_QUESTION_PATTERN.finditer(text))
        if not candidates:
            return [(None, text)]

        # Keep only forward-moving number anchors to avoid splitting on choice lines like "1) ...".
        matches: list[re.Match[str]] = [candidates[0]]
        last_num = int(candidates[0].group(1))
        for candidate in candidates[1:]:
            num = int(candidate.group(1))
            if num > last_num:
                matches.append(candidate)
                last_num = num

        items: list[tuple[str | None, str]] = []
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            if chunk:
                items.append((match.group(1), chunk))

        return items or [(None, text)]

    @staticmethod
    def _build_structure(question_text: str) -> dict[str, Any]:
        choices = [
            {"label": str(i + 1), "text": item.group(1).strip()}
            for i, item in enumerate(_CHOICE_PATTERN.finditer(question_text))
            if item.group(1).strip()
        ]
        return {
            "parsed_v1": {
                "stem": question_text,
                "choices": choices,
            }
        }

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _to_confidence(value: Any, default: float) -> float:
        try:
            parsed = float(value)
        except Exception:
            return max(0.0, min(1.0, default))
        return max(0.0, min(1.0, parsed))

    def _can_use_llm(self) -> bool:
        if not self.llm_enabled or self.llm is None:
            return False
        provider = str(getattr(self.llm, "provider_name", "") or "").lower()
        return provider != "mock"

    def _can_use_multimodal_llm(self) -> bool:
        if not self._can_use_llm() or self.llm is None:
            return False
        multimodal = getattr(self.llm, "generate_structured_from_media", None)
        return callable(multimodal)

    def _can_use_secondary_ocr(self) -> bool:
        provider = str(getattr(self.ocr_fallback, "provider_name", "") or "").lower()
        return provider not in {"", "mock"}

    def _extract_with_secondary_ocr(self, payload: bytes) -> tuple[str, float, str] | None:
        if not self._can_use_secondary_ocr():
            return None
        provider = str(getattr(self.ocr_fallback, "provider_name", "") or "ocr_fallback")
        try:
            extracted = self.ocr_fallback.extract(payload)
        except Exception:
            return None

        text = self._normalize_text(str(extracted.get("text") or ""))
        if not text:
            return None
        confidence = float(extracted.get("confidence") or 0.75)
        return text, max(0.0, min(1.0, confidence)), provider

    def _refine_with_llm(
        self,
        *,
        raw_text: str,
        source_type: str,
        engine: str,
        questions: list[ExtractedQuestion],
    ) -> list[ExtractedQuestion] | None:
        if not self._can_use_llm() or not raw_text.strip() or not questions:
            return None

        preview = [
            {
                "orderIndex": q.order_index,
                "numberLabel": q.number_label,
                "text": q.text[:1000],
                "confidence": q.confidence,
            }
            for q in questions
        ]

        system_prompt = (
            "You are a Korean exam document structuring assistant. "
            "Given noisy OCR text, return corrected question-level JSON only."
        )
        prompt = (
            f"sourceType={source_type}\n"
            f"engine={engine}\n"
            f"ocrRawText={raw_text[:12000]}\n"
            f"preSplitQuestions={json.dumps(preview, ensure_ascii=False)}\n"
            "Task:\n"
            "1) Correct broken OCR text per question.\n"
            "2) Keep question order and number labels where possible.\n"
            "3) Fill metadata fields when inferable; otherwise use 'unknown'.\n"
        )

        try:
            data = self.llm.generate_structured(
                prompt=prompt,
                schema=_LLM_REFINEMENT_SCHEMA,
                system_prompt=system_prompt,
                model=self.llm_model,
            )
        except Exception:
            return None

        if not isinstance(data, dict):
            return None
        refined_items = data.get("questions")
        if not isinstance(refined_items, list) or not refined_items:
            return None

        refined_questions: list[ExtractedQuestion] = []
        for idx, item in enumerate(refined_items, start=1):
            if not isinstance(item, dict):
                continue
            text = self._normalize_text(str(item.get("text") or ""))
            if not text:
                continue

            seed = questions[min(idx - 1, len(questions) - 1)]
            order_index = self._to_int(item.get("orderIndex"), idx)
            if order_index <= 0:
                order_index = idx

            number_label = str(item.get("numberLabel") or seed.number_label or order_index)
            confidence = self._to_confidence(item.get("confidence"), seed.confidence + 0.03)

            metadata = dict(seed.metadata or {})
            metadata["subject"] = str(item.get("subject") or metadata.get("subject") or "unknown")
            metadata["unit"] = str(item.get("unit") or metadata.get("unit") or "unknown")
            metadata["difficulty"] = str(item.get("difficulty") or metadata.get("difficulty") or "unknown")
            metadata["questionType"] = str(item.get("questionType") or metadata.get("questionType") or "unknown")
            metadata["answerFormat"] = str(item.get("answerFormat") or metadata.get("answerFormat") or "unknown")
            metadata["engine"] = f"{engine}+llm"
            metadata["llmRefined"] = True
            metadata["llmModel"] = self.llm_model or str(getattr(self.llm, "model_name", "") or "")

            refined_questions.append(
                ExtractedQuestion(
                    order_index=order_index,
                    number_label=number_label,
                    text=text,
                    confidence=confidence,
                    metadata=metadata,
                    structure=self._build_structure(text),
                )
            )

        if not refined_questions:
            return None

        refined_questions.sort(key=lambda q: (q.order_index, q.number_label or ""))
        return refined_questions

    def _extract_pdf(self, payload: bytes) -> tuple[str, float, str] | None:
        try:
            import fitz  # type: ignore
        except Exception:
            return None

        try:
            doc = fitz.open(stream=payload, filetype="pdf")
            try:
                page_texts = [self._normalize_text(page.get_text("text")) for page in doc]
                text = self._normalize_text("\n\n".join(item for item in page_texts if item))
                if text:
                    return text, 0.98, "pymupdf"

                # Image-based PDF fallback: render pages then OCR each page.
                ocr_page_texts: list[str] = []
                ocr_engines: list[str] = []
                for page in doc:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    page_png = pix.tobytes("png")
                    extracted = self._extract_image(page_png)
                    if extracted is None:
                        continue
                    ocr_engines.append(extracted[2])
                    page_text = self._normalize_text(extracted[0])
                    if page_text:
                        ocr_page_texts.append(page_text)

                ocr_text = self._normalize_text("\n\n".join(ocr_page_texts))
                if ocr_text:
                    primary_engine = ocr_engines[0] if ocr_engines else "pytesseract"
                    if primary_engine.endswith("_pdf"):
                        return ocr_text, 0.8, primary_engine
                    return ocr_text, 0.8, f"{primary_engine}_pdf"
                return None
            finally:
                doc.close()
        except Exception:
            return None

    @staticmethod
    def _preprocess_image(payload: bytes) -> bytes:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
        except Exception:
            return payload

        try:
            arr = np.frombuffer(payload, dtype=np.uint8)
            image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if image is None:
                return payload

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            denoised = cv2.medianBlur(gray, 3)
            _, encoded = cv2.imencode(".png", denoised)
            if not encoded.any():
                return payload
            return encoded.tobytes()
        except Exception:
            return payload

    def _extract_image(self, payload: bytes) -> tuple[str, float, str] | None:
        processed = self._preprocess_image(payload)

        # If a stronger OCR adapter is configured (e.g., Google Vision),
        # try it first for better robustness on noisy scans.
        secondary = self._extract_with_secondary_ocr(processed)
        if secondary is not None:
            return secondary

        try:
            from PIL import Image  # type: ignore
            import pytesseract  # type: ignore
        except Exception:
            return self._extract_with_secondary_ocr(processed)

        try:
            image = Image.open(io.BytesIO(processed))
            text = self._normalize_text(
                pytesseract.image_to_string(
                    image,
                    lang=self.ocr_lang,
                    config="--oem 1 --psm 6",
                )
            )
            if not text:
                text = self._normalize_text(pytesseract.image_to_string(image))
            if not text:
                return self._extract_with_secondary_ocr(processed)
            return text, 0.82, "pytesseract"
        except Exception:
            return self._extract_with_secondary_ocr(processed)

    def _extract_with_fallback(self, payload: bytes) -> tuple[str, float, str]:
        extracted = self.ocr_fallback.extract(payload)
        text = self._normalize_text(str(extracted.get("text") or ""))
        if text.startswith("[mock]"):
            text = (
                "OCR 자동추출 결과를 확보하지 못해 임시 결과를 표시합니다. "
                "Tesseract 설치/언어 설정 또는 문서 품질(해상도, 기울기)을 확인해 주세요."
            )
        if not text:
            text = (
                "OCR 텍스트를 추출하지 못했습니다. "
                "지원 형식(PDF/PNG/JPG)인지 확인하고 다시 시도해 주세요."
            )
        confidence = float(extracted.get("confidence") or 0.5)
        return text, confidence, "ocr_fallback"

    @staticmethod
    def _media_source_type(content_type: str | None, filename: str | None) -> str:
        lower_name = (filename or "").lower()
        mime = (content_type or "").lower()
        if mime.startswith("application/pdf") or lower_name.endswith(".pdf"):
            return "pdf"
        if mime.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg")):
            return "image"
        return "binary"

    def _encode_compact_image(self, image) -> tuple[bytes, str]:
        try:
            from PIL import Image
        except Exception:
            raise RuntimeError("Pillow is not available")

        work = image.convert("RGB")
        max_side = 2200
        quality = 85
        resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")

        while True:
            resized = work
            longest = max(resized.width, resized.height)
            if longest > max_side:
                ratio = max_side / float(longest)
                resized = resized.resize(
                    (max(1, int(resized.width * ratio)), max(1, int(resized.height * ratio))),
                    resampling,
                )

            buf = io.BytesIO()
            resized.save(buf, format="JPEG", quality=quality, optimize=True)
            packed = buf.getvalue()
            if len(packed) <= _MAX_GEMINI_MEDIA_BYTES:
                return packed, "image/jpeg"

            if max_side <= 900 and quality <= 55:
                return packed, "image/jpeg"
            max_side = max(900, int(max_side * 0.85))
            quality = max(55, quality - 10)

    def _prepare_image_media_for_llm(
        self,
        *,
        payload: bytes,
    ) -> tuple[bytes, str] | None:
        try:
            from PIL import Image
        except Exception:
            return None

        processed = self._preprocess_image(payload)
        try:
            image = Image.open(io.BytesIO(processed)).convert("RGB")
        except Exception:
            return None
        return self._encode_compact_image(image)

    def _extract_with_gemini_raw_text(
        self,
        *,
        media_bytes: bytes,
        media_mime_type: str,
        source_type: str,
        page_index: int,
    ) -> tuple[list[ExtractedQuestion], str]:
        if self.llm is None:
            raise RuntimeError("Gemini raw-text fallback is unavailable.")

        system_prompt = (
            "You are a Korean exam OCR assistant. Read the attached document image and return strict JSON only."
        )
        prompt = (
            "Extract all visible text from the document preserving line breaks as much as possible. "
            "Do not summarize."
        )
        try:
            data = self.llm.generate_structured_from_media(
                prompt=prompt,
                schema=_LLM_MEDIA_RAW_TEXT_SCHEMA,
                media_bytes=media_bytes,
                media_mime_type=media_mime_type,
                system_prompt=system_prompt,
                model=self.llm_model,
            )
        except Exception as exc:
            raise RuntimeError(f"Gemini raw-text fallback failed: {exc}") from exc

        raw_text = self._normalize_text(str((data or {}).get("rawText") or ""))
        if not raw_text:
            raise RuntimeError("Gemini multimodal extraction returned empty questions and empty rawText.")

        split_items = self._split_questions(raw_text)
        if not split_items:
            split_items = [(None, raw_text)]

        questions: list[ExtractedQuestion] = []
        for idx, (number_label, question_text) in enumerate(split_items, start=1):
            conf = max(0.55, 0.85 - (0.02 * (idx - 1)))
            metadata = {
                "subject": "unknown",
                "unit": "unknown",
                "difficulty": "unknown",
                "questionType": "unknown",
                "answerFormat": "unknown",
                "source": "uploaded",
                "engine": "gemini_vision_text",
                "sourceType": source_type,
                "pageIndex": page_index,
                "llmRefined": True,
                "llmModel": self.llm_model or str(getattr(self.llm, "model_name", "") or ""),
            }
            questions.append(
                ExtractedQuestion(
                    order_index=idx,
                    number_label=number_label or str(idx),
                    text=question_text,
                    confidence=conf,
                    metadata=metadata,
                    structure=self._build_structure(question_text),
                )
            )
        return questions, raw_text

    @staticmethod
    def _column_key(q: ExtractedQuestion) -> str:
        hint = (q.metadata or {}).get("cropHint")
        if not isinstance(hint, dict):
            return "full"
        left = hint.get("leftRatio")
        if left is None:
            return "full"
        return "left" if float(left) < 0.4 else "right"

    @staticmethod
    def _postprocess_crop_hints(
        questions: list[ExtractedQuestion],
    ) -> list[ExtractedQuestion]:
        if not questions:
            return questions

        _MIN_HEIGHT_RATIO = 0.05

        for q in questions:
            hint = (q.metadata or {}).get("cropHint")
            if not isinstance(hint, dict):
                continue
            top = hint.get("topRatio", 0)
            bottom = hint.get("bottomRatio", 0)
            height = bottom - top
            if 0 < height < _MIN_HEIGHT_RATIO:
                mid = (top + bottom) / 2
                hint["topRatio"] = round(max(0.0, mid - _MIN_HEIGHT_RATIO / 2), 5)
                hint["bottomRatio"] = round(min(1.0, mid + _MIN_HEIGHT_RATIO / 2), 5)

        col_key = DocumentExtractionPipeline._column_key
        by_col: dict[str, list[ExtractedQuestion]] = {"full": [], "left": [], "right": []}
        for q in questions:
            by_col.setdefault(col_key(q), []).append(q)

        sort_by_top = lambda q: (q.metadata or {}).get("cropHint", {}).get("topRatio", 0)
        for group in by_col.values():
            group.sort(key=sort_by_top)
            for i in range(1, len(group)):
                prev_hint = (group[i - 1].metadata or {}).get("cropHint")
                curr_hint = (group[i].metadata or {}).get("cropHint")
                if not isinstance(prev_hint, dict) or not isinstance(curr_hint, dict):
                    continue
                prev_bottom = prev_hint.get("bottomRatio", 0)
                curr_top = curr_hint.get("topRatio", 0)
                if curr_top < prev_bottom:
                    midpoint = (prev_bottom + curr_top) / 2
                    prev_hint["bottomRatio"] = round(midpoint, 5)
                    curr_hint["topRatio"] = round(midpoint, 5)

        reordered = by_col.get("full", []) + by_col.get("left", []) + by_col.get("right", [])
        for idx, q in enumerate(reordered, start=1):
            q.order_index = idx
        return reordered

    def _extract_with_gemini_media(
        self,
        *,
        media_bytes: bytes,
        media_mime_type: str,
        source_type: str,
        page_index: int,
    ) -> tuple[list[ExtractedQuestion], str]:
        if self.llm is None:
            raise RuntimeError("gemini_full mode requires a multimodal LLM backend.")

        system_prompt = (
            "You are an exam parsing engine. Read the attached document image and "
            "return strict JSON only according to schema."
        )
        prompt = (
            f"pageIndex={page_index}\n"
            "Parse this Korean exam sheet into per-question records.\n"
            "Rules:\n"
            "1) Detect the page layout: single-column or two-column.\n"
            "2) For two-column layouts, process in reading order: "
            "left column top-to-bottom first, then right column top-to-bottom.\n"
            "3) Keep numberLabel exactly as visible.\n"
            "4) text must contain the full question body and all options.\n"
            "5) confidence is 0~1.\n"
            "6) cropTopRatio/cropBottomRatio are normalized vertical positions (0~1) "
            "on this single page image. They must tightly enclose only that question.\n"
            "7) cropLeftRatio/cropRightRatio are normalized horizontal positions (0~1). "
            "Left-column questions: cropLeftRatio~0.0, cropRightRatio~0.5. "
            "Right-column questions: cropLeftRatio~0.5, cropRightRatio~1.0. "
            "Full-width questions (headers, single-column): cropLeftRatio=0.0, cropRightRatio=1.0.\n"
            "8) Crop regions must NOT overlap between questions.\n"
            "9) If any crop ratio is uncertain, return null for that field.\n"
            "10) If metadata cannot be inferred, use 'unknown'."
        )

        try:
            data = self.llm.generate_structured_from_media(
                prompt=prompt,
                schema=_LLM_MEDIA_EXTRACTION_SCHEMA,
                media_bytes=media_bytes,
                media_mime_type=media_mime_type,
                system_prompt=system_prompt,
                model=self.llm_model,
            )
        except Exception as exc:
            try:
                return self._extract_with_gemini_raw_text(
                    media_bytes=media_bytes,
                    media_mime_type=media_mime_type,
                    source_type=source_type,
                    page_index=page_index,
                )
            except Exception as raw_exc:
                raise RuntimeError(
                    f"structured extraction failed: {exc}; raw-text fallback failed: {raw_exc}"
                ) from raw_exc

        items = data.get("questions") if isinstance(data, dict) else None
        if not isinstance(items, list):
            items = []
        if not items:
            return self._extract_with_gemini_raw_text(
                media_bytes=media_bytes,
                media_mime_type=media_mime_type,
                source_type=source_type,
                page_index=page_index,
            )

        questions: list[ExtractedQuestion] = []
        raw_chunks: list[str] = []
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            text = self._normalize_text(str(item.get("text") or ""))
            if not text:
                continue
            order_index = self._to_int(item.get("orderIndex"), idx)
            if order_index <= 0:
                order_index = idx
            number_label = str(item.get("numberLabel") or order_index)
            confidence = self._to_confidence(item.get("confidence"), 0.9)

            metadata = {
                "subject": str(item.get("subject") or "unknown"),
                "unit": str(item.get("unit") or "unknown"),
                "difficulty": str(item.get("difficulty") or "unknown"),
                "questionType": str(item.get("questionType") or "unknown"),
                "answerFormat": str(item.get("answerFormat") or "unknown"),
                "source": "uploaded",
                "engine": "gemini_vision",
                "sourceType": source_type,
                "pageIndex": page_index,
                "llmRefined": True,
                "llmModel": self.llm_model or str(getattr(self.llm, "model_name", "") or ""),
            }

            try:
                top_ratio = float(item.get("cropTopRatio"))
                bottom_ratio = float(item.get("cropBottomRatio"))
                top_ratio = max(0.0, min(1.0, top_ratio))
                bottom_ratio = max(0.0, min(1.0, bottom_ratio))
                if bottom_ratio > top_ratio:
                    crop_hint: dict[str, Any] = {
                        "pageIndex": page_index,
                        "topRatio": round(top_ratio, 5),
                        "bottomRatio": round(bottom_ratio, 5),
                    }
                    try:
                        left_ratio = float(item.get("cropLeftRatio"))
                        right_ratio = float(item.get("cropRightRatio"))
                        left_ratio = max(0.0, min(1.0, left_ratio))
                        right_ratio = max(0.0, min(1.0, right_ratio))
                        if right_ratio > left_ratio:
                            crop_hint["leftRatio"] = round(left_ratio, 5)
                            crop_hint["rightRatio"] = round(right_ratio, 5)
                    except (TypeError, ValueError):
                        pass
                    metadata["cropHint"] = crop_hint
            except (TypeError, ValueError):
                pass

            questions.append(
                ExtractedQuestion(
                    order_index=order_index,
                    number_label=number_label,
                    text=text,
                    confidence=confidence,
                    metadata=metadata,
                    structure=self._build_structure(text),
                )
            )
            raw_chunks.append(text)

        if not questions:
            raise RuntimeError("structured extraction returned no valid question payloads.")

        questions = self._postprocess_crop_hints(questions)
        raw_text = self._normalize_text("\n\n".join(raw_chunks))
        return questions, raw_text

    def _extract_with_gemini_full(
        self,
        *,
        payload: bytes,
        content_type: str | None,
        filename: str | None,
    ) -> tuple[list[ExtractedQuestion], str, str, str]:
        if not self._can_use_multimodal_llm() or self.llm is None:
            raise RuntimeError("gemini_full mode requires a multimodal LLM backend.")

        source_type = self._media_source_type(content_type, filename)
        all_questions: list[ExtractedQuestion] = []
        raw_chunks: list[str] = []

        if source_type == "pdf":
            pages = QuestionCropper._render_pages(payload=payload, content_type=content_type, filename=filename)
            if not pages:
                raise RuntimeError("gemini_page_extract_failed(page=0): could not render PDF pages.")
            for page_idx, page_image in enumerate(pages, start=1):
                try:
                    media_bytes, media_mime_type = self._encode_compact_image(page_image)
                    page_questions, raw_text = self._extract_with_gemini_media(
                        media_bytes=media_bytes,
                        media_mime_type=media_mime_type,
                        source_type=source_type,
                        page_index=page_idx,
                    )
                except Exception as exc:
                    raise RuntimeError(f"gemini_page_extract_failed(page={page_idx}): {exc}") from exc
                all_questions.extend(page_questions)
                raw_chunks.append(raw_text)
        elif source_type == "image":
            prepared = self._prepare_image_media_for_llm(payload=payload)
            if prepared is None:
                raise RuntimeError("gemini_extract_failed(page=1): could not prepare image payload.")
            media_bytes, media_mime_type = prepared
            page_questions, raw_text = self._extract_with_gemini_media(
                media_bytes=media_bytes,
                media_mime_type=media_mime_type,
                source_type=source_type,
                page_index=1,
            )
            all_questions.extend(page_questions)
            raw_chunks.append(raw_text)
        else:
            raise RuntimeError("gemini_extract_failed: unsupported media type for gemini_full.")

        if not all_questions:
            raise RuntimeError("gemini_extract_failed: no questions extracted.")

        all_questions.sort(
            key=lambda q: (
                int((q.metadata or {}).get("pageIndex") or 0),
                int(q.order_index or 0),
                str(q.number_label or ""),
            )
        )
        for idx, question in enumerate(all_questions, start=1):
            question.order_index = idx
            if not question.number_label:
                question.number_label = str(idx)

        engines = {str((item.metadata or {}).get("engine") or "") for item in all_questions}
        if source_type == "pdf":
            if engines == {"gemini_vision"}:
                engine = "gemini_vision_pages"
            elif engines == {"gemini_vision_text"}:
                engine = "gemini_vision_text_pages"
            else:
                engine = "gemini_vision_mixed"
        else:
            if engines == {"gemini_vision"}:
                engine = "gemini_vision"
            elif engines == {"gemini_vision_text"}:
                engine = "gemini_vision_text"
            else:
                engine = "gemini_vision_mixed"
        raw_text = self._normalize_text("\n\n".join(chunk for chunk in raw_chunks if chunk))
        return all_questions, engine, raw_text, source_type

    def extract(
        self,
        *,
        payload: bytes,
        content_type: str | None,
        filename: str | None,
    ) -> ExtractionResult:
        if self.extraction_mode == "gemini_full":
            questions, engine, raw_text, source_type = self._extract_with_gemini_full(
                payload=payload,
                content_type=content_type,
                filename=filename,
            )
            avg_conf = sum(item.confidence for item in questions) / max(1, len(questions))
            return ExtractionResult(
                questions=questions,
                engine=engine,
                average_confidence=avg_conf,
                raw_text=raw_text,
                source_type=source_type,
            )

        lower_name = (filename or "").lower()
        mime = (content_type or "").lower()

        source_type = "binary"
        extracted: tuple[str, float, str] | None = None

        if mime.startswith("application/pdf") or lower_name.endswith(".pdf"):
            source_type = "pdf"
            extracted = self._extract_pdf(payload)
        elif mime.startswith("image/") or lower_name.endswith((".png", ".jpg", ".jpeg")):
            source_type = "image"
            extracted = self._extract_image(payload)

        if extracted is None and payload:
            try:
                decoded = self._normalize_text(payload.decode("utf-8"))
                if decoded:
                    extracted = (decoded, 0.7, "utf8_decode")
                    source_type = "text"
            except Exception:
                extracted = None

        if extracted is None:
            extracted = self._extract_with_fallback(payload)

        text, base_confidence, engine = extracted
        split_items = self._split_questions(text)
        if not split_items:
            split_items = [(None, text or "[empty]")]

        questions: list[ExtractedQuestion] = []
        for idx, (number_label, question_text) in enumerate(split_items, start=1):
            conf = max(0.0, min(1.0, base_confidence - (0.01 * (idx - 1))))
            metadata = {
                "subject": "unknown",
                "unit": "unknown",
                "difficulty": "unknown",
                "source": "uploaded",
                "engine": engine,
                "sourceType": source_type,
            }
            questions.append(
                ExtractedQuestion(
                    order_index=idx,
                    number_label=number_label or str(idx),
                    text=question_text,
                    confidence=conf,
                    metadata=metadata,
                    structure=self._build_structure(question_text),
                )
            )

        llm_refined_questions = self._refine_with_llm(
            raw_text=text,
            source_type=source_type,
            engine=engine,
            questions=questions,
        )
        if llm_refined_questions:
            questions = llm_refined_questions
            engine = f"{engine}+llm"

        avg_conf = sum(item.confidence for item in questions) / max(1, len(questions))
        return ExtractionResult(
            questions=questions,
            engine=engine,
            average_confidence=avg_conf,
            raw_text=text,
            source_type=source_type,
        )

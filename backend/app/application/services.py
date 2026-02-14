from __future__ import annotations

import time
from typing import Any, Protocol

from app.infra.ports.llm import LLMPort
from app.infra.ports.ocr import OCRPort
from app.infra.ports.storage import StoragePort
from app.workers.extraction import DocumentExtractionPipeline, QuestionCropper

_ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
)


class DocumentStorePort(Protocol):
    def create_document(self, *, filename: str | None, mime: str | None, size: int | None) -> dict[str, str]:
        ...


class DocumentJobStorePort(Protocol):
    def mark_job_running(self, *, job_id: str, stage: str, percent: float) -> bool:
        ...

    def complete_job(
        self,
        *,
        job_id: str,
        stage: str,
        percent: float,
        set_status: str,
        questions: list[dict[str, Any]],
    ) -> bool:
        ...

    def fail_job(self, *, job_id: str, error_message: str) -> bool:
        ...


class ReviewStorePort(Protocol):
    def review_question(
        self,
        *,
        question_id: str,
        reviewer: str,
        review_status: str,
        note: str | None,
        metadata_patch: dict[str, Any] | None,
    ):
        ...


class DocumentApplicationService:
    def __init__(self, *, store: DocumentStorePort, storage: StoragePort):
        self.store = store
        self.storage = storage

    def create_document(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        payload: bytes,
    ) -> dict[str, str]:
        if content_type and not content_type.startswith(_ALLOWED_MIME_PREFIXES):
            raise ValueError("Unsupported file format. Use PDF/PNG/JPG.")

        result = self.store.create_document(
            filename=filename,
            mime=content_type,
            size=len(payload),
        )

        set_id = result["setId"]
        ext = (filename or "bin").rsplit(".", 1)[-1].lower()
        key = f"{set_id}/source.{ext}"
        self.storage.save_bytes(key, payload, content_type)
        return result


class DocumentProcessingService:
    def __init__(
        self,
        *,
        store: DocumentJobStorePort,
        ocr: OCRPort,
        storage: StoragePort,
        llm: LLMPort | None = None,
        stage_delay_ms: int = 0,
        ocr_lang: str = "kor+eng",
        extraction_llm_enabled: bool = True,
        extraction_llm_model: str | None = None,
        extraction_mode: str = "hybrid",
    ):
        self.store = store
        self.ocr = ocr
        self.storage = storage
        self.pipeline = DocumentExtractionPipeline(
            ocr_fallback=ocr,
            ocr_lang=ocr_lang,
            llm=llm,
            llm_enabled=extraction_llm_enabled,
            llm_model=extraction_llm_model,
            extraction_mode=extraction_mode,
        )
        self.cropper = QuestionCropper(storage=storage, ocr_lang=ocr_lang, secondary_ocr=ocr)
        self.stage_delay_seconds = max(0.0, stage_delay_ms / 1000.0)

    def _delay(self) -> None:
        if self.stage_delay_seconds > 0:
            time.sleep(self.stage_delay_seconds)

    def process_document(
        self,
        *,
        job_id: str,
        set_id: str,
        filename: str | None,
        content_type: str | None,
        payload: bytes,
    ) -> None:
        gemini_mode = self.pipeline.extraction_mode == "gemini_full"

        if not self.store.mark_job_running(job_id=job_id, stage="preprocess", percent=15.0):
            return
        self._delay()

        if gemini_mode:
            if not self.store.mark_job_running(job_id=job_id, stage="gemini_page_extract", percent=60.0):
                return
            self._delay()
        else:
            if not self.store.mark_job_running(job_id=job_id, stage="layout", percent=45.0):
                return
            self._delay()
            if not self.store.mark_job_running(job_id=job_id, stage="ocr", percent=75.0):
                return
            self._delay()

        try:
            result = self.pipeline.extract(
                payload=payload,
                content_type=content_type,
                filename=filename,
            )

            if not self.store.mark_job_running(
                job_id=job_id,
                stage="merge" if gemini_mode else "split",
                percent=82.0 if gemini_mode else 90.0,
            ):
                return
            self._delay()

            questions: list[dict[str, Any]] = []
            for item in result.questions:
                review_status = "auto_ok" if item.confidence >= 0.9 else "auto_flagged"
                metadata = dict(item.metadata)
                metadata["sourceMime"] = content_type
                metadata["sourceFilename"] = filename
                metadata["pipelineVersion"] = "phaseA-gemini-pages-1" if gemini_mode else "phaseA-mvp-1"
                metadata["averageConfidence"] = round(result.average_confidence, 4)

                questions.append(
                    {
                        "number_label": item.number_label,
                        "order_index": item.order_index,
                        "review_status": review_status,
                        "confidence": item.confidence,
                        "ocr_text": item.text,
                        "metadata": metadata,
                        "structure": item.structure,
                    }
                )

            if not self.store.mark_job_running(job_id=job_id, stage="crop", percent=92.0):
                return
            self._delay()

            crop_traces = self.cropper.create_and_store_with_trace(
                set_id=set_id,
                payload=payload,
                content_type=content_type,
                filename=filename,
                question_count=len(questions),
                question_labels=[str(item.get("number_label") or "") for item in questions],
                question_crop_hints=[
                    ((item.get("metadata") or {}).get("cropHint") if isinstance(item.get("metadata"), dict) else None)
                    for item in questions
                ],
            )
            for idx, trace in enumerate(crop_traces):
                if idx >= len(questions):
                    continue
                metadata = dict(questions[idx].get("metadata") or {})
                url = trace.get("url")
                if url:
                    metadata["croppedImageUrl"] = url
                crop_source = trace.get("cropSource")
                if crop_source:
                    metadata["cropSource"] = crop_source
                page_index = trace.get("pageIndex")
                if page_index and not metadata.get("pageIndex"):
                    metadata["pageIndex"] = page_index
                questions[idx]["metadata"] = metadata

            set_status = (
                "ready"
                if questions and all(q["review_status"] == "auto_ok" for q in questions)
                else "needs_review"
            )
            self.store.complete_job(
                job_id=job_id,
                stage="completed",
                percent=100.0,
                set_status=set_status,
                questions=questions,
            )
        except Exception as exc:  # pragma: no cover
            self.store.fail_job(job_id=job_id, error_message=str(exc)[:400])


class ReviewApplicationService:
    def __init__(self, *, store: ReviewStorePort):
        self.store = store

    def apply_review(
        self,
        *,
        question_id: str,
        reviewer: str,
        review_status: str,
        note: str | None,
        metadata_patch: dict[str, Any] | None,
    ):
        return self.store.review_question(
            question_id=question_id,
            reviewer=reviewer,
            review_status=review_status,
            note=note,
            metadata_patch=metadata_patch,
        )

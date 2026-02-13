from __future__ import annotations

import time
from typing import Any, Protocol

from app.infra.ports.ocr import OCRPort
from app.infra.ports.storage import StoragePort

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
    def __init__(self, *, store: DocumentJobStorePort, ocr: OCRPort, stage_delay_ms: int = 0):
        self.store = store
        self.ocr = ocr
        self.stage_delay_seconds = max(0.0, stage_delay_ms / 1000.0)

    def _delay(self) -> None:
        if self.stage_delay_seconds > 0:
            time.sleep(self.stage_delay_seconds)

    def process_document(
        self,
        *,
        job_id: str,
        filename: str | None,
        content_type: str | None,
        payload: bytes,
    ) -> None:
        if not self.store.mark_job_running(job_id=job_id, stage="preprocess", percent=15.0):
            return
        self._delay()

        if not self.store.mark_job_running(job_id=job_id, stage="layout", percent=45.0):
            return
        self._delay()

        if not self.store.mark_job_running(job_id=job_id, stage="ocr", percent=75.0):
            return
        self._delay()

        try:
            ocr_payload = self.ocr.extract(payload)
            ocr_text = str(ocr_payload.get("text") or "").strip() or "[mock] OCR text"
            confidence = float(ocr_payload.get("confidence") or 0.0)

            review_status = "auto_ok" if confidence >= 0.9 else "auto_flagged"
            set_status = "ready" if review_status == "auto_ok" else "needs_review"

            question = {
                "number_label": "1",
                "order_index": 1,
                "review_status": review_status,
                "confidence": confidence,
                "ocr_text": ocr_text,
                "metadata": {
                    "subject": "unknown",
                    "unit": "unknown",
                    "difficulty": "unknown",
                    "source": "uploaded",
                    "sourceMime": content_type,
                    "sourceFilename": filename,
                },
                "structure": {
                    "parsed_v1": {
                        "stem": ocr_text,
                        "tokens": ocr_payload.get("tokens", []),
                    }
                },
            }
            self.store.complete_job(
                job_id=job_id,
                stage="completed",
                percent=100.0,
                set_status=set_status,
                questions=[question],
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

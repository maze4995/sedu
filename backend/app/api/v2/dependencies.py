from __future__ import annotations

from functools import lru_cache

from app.application.services import DocumentApplicationService, DocumentProcessingService, ReviewApplicationService
from app.core.config import get_settings
from app.infra.db.store import DatabaseStore
from app.infra.llm.mock import MockLLM
from app.infra.ocr.mock import MockOCR
from app.infra.ports.llm import LLMPort
from app.infra.ports.ocr import OCRPort
from app.infra.ports.storage import StoragePort
from app.infra.storage.local import LocalFileStorage
from app.infra.storage.s3 import S3Storage


@lru_cache(maxsize=1)
def get_store() -> DatabaseStore:
    return DatabaseStore()


@lru_cache(maxsize=1)
def get_storage() -> StoragePort:
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("SEDU_S3_BUCKET is required when SEDU_STORAGE_BACKEND=s3")
        return S3Storage(bucket=settings.s3_bucket, region=settings.s3_region)
    return LocalFileStorage(base_dir=settings.upload_dir)


@lru_cache(maxsize=1)
def get_ocr() -> OCRPort:
    return MockOCR()


@lru_cache(maxsize=1)
def get_llm() -> LLMPort:
    return MockLLM()


def get_document_service() -> DocumentApplicationService:
    return DocumentApplicationService(store=get_store(), storage=get_storage())


def get_document_processing_service() -> DocumentProcessingService:
    settings = get_settings()
    return DocumentProcessingService(
        store=get_store(),
        ocr=get_ocr(),
        stage_delay_ms=settings.job_stage_delay_ms,
    )


def get_review_service() -> ReviewApplicationService:
    return ReviewApplicationService(store=get_store())

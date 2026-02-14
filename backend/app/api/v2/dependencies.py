from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from app.application.generation import AIGenerationService
from app.application.services import DocumentApplicationService, DocumentProcessingService, ReviewApplicationService
from app.core.config import get_settings
from app.infra.db.store import DatabaseStore
from app.infra.llm.gemini import GeminiLLM
from app.infra.llm.mock import MockLLM
from app.infra.ocr.mock import MockOCR
from app.infra.ports.llm import LLMPort
from app.infra.ports.ocr import OCRPort
from app.infra.ports.storage import StoragePort
from app.infra.storage.local import LocalFileStorage
from app.infra.storage.s3 import S3Storage

_LANG_HINT_MAP = {
    "kor": "ko",
    "eng": "en",
    "jpn": "ja",
    "chi_sim": "zh-CN",
    "chi_tra": "zh-TW",
}


def _to_vision_language_hints(ocr_lang: str) -> list[str]:
    # Tesseract style: "kor+eng" -> Vision style hints: ["ko", "en"]
    hints: list[str] = []
    for item in (ocr_lang or "").replace(",", "+").split("+"):
        key = item.strip().lower()
        if not key:
            continue
        hints.append(_LANG_HINT_MAP.get(key, key))
    return hints


def _resolve_google_credentials_path() -> str | None:
    raw = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if not raw:
        return None

    backend_root = Path(__file__).resolve().parents[3]
    path = Path(raw)
    candidates: list[Path] = []

    if path.is_absolute():
        candidates.append(path)
        # Common local mistake: "/credentials/..." while file is "backend/credentials/..."
        candidates.append((backend_root / raw.lstrip("/")).resolve())
    else:
        candidates.append((backend_root / path).resolve())

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


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
    settings = get_settings()
    if settings.ocr_backend == "vision":
        from app.infra.ocr.google_vision import GoogleVisionOCR

        resolved_credentials = _resolve_google_credentials_path()
        if resolved_credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = resolved_credentials
        else:
            raw = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
            raise RuntimeError(
                "Failed to initialize Vision OCR. GOOGLE_APPLICATION_CREDENTIALS is invalid. "
                f"Current value='{raw or '(empty)'}'. "
                "Expected an existing service-account JSON file path "
                "(e.g. backend/credentials/service-account.json)."
            )

        try:
            return GoogleVisionOCR(
                language_hints=_to_vision_language_hints(settings.ocr_lang),
                timeout_seconds=settings.llm_timeout_seconds,
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to initialize Vision OCR. Check GOOGLE_APPLICATION_CREDENTIALS "
                "and verify service account has Vision API access."
            ) from exc
    return MockOCR()


@lru_cache(maxsize=1)
def get_llm() -> LLMPort:
    settings = get_settings()
    if settings.llm_backend == "gemini" and settings.gemini_api_key:
        return GeminiLLM(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    return MockLLM()


def get_document_service() -> DocumentApplicationService:
    return DocumentApplicationService(store=get_store(), storage=get_storage())


def get_document_processing_service() -> DocumentProcessingService:
    settings = get_settings()
    return DocumentProcessingService(
        store=get_store(),
        ocr=get_ocr(),
        storage=get_storage(),
        llm=get_llm(),
        stage_delay_ms=settings.job_stage_delay_ms,
        ocr_lang=settings.ocr_lang,
        extraction_llm_enabled=settings.extraction_llm_enabled,
        extraction_llm_model=settings.gemini_model,
        extraction_mode=settings.extraction_mode,
    )


def get_review_service() -> ReviewApplicationService:
    return ReviewApplicationService(store=get_store())


def get_generation_service() -> AIGenerationService:
    return AIGenerationService(llm=get_llm(), store=get_store())


async def provide_store() -> DatabaseStore:
    return get_store()


async def provide_document_service() -> DocumentApplicationService:
    return get_document_service()


async def provide_document_processing_service() -> DocumentProcessingService:
    return get_document_processing_service()


async def provide_review_service() -> ReviewApplicationService:
    return get_review_service()


async def provide_generation_service() -> AIGenerationService:
    return get_generation_service()

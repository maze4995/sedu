from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_dotenv() -> None:
    if os.getenv("SEDU_SKIP_DOTENV") == "1":
        return

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
    except Exception:
        return

    load_dotenv(env_path, override=True)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_non_negative_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    raw = value.strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class Settings:
    env: str
    app_name: str
    cors_origins: list[str]
    upload_dir: Path
    job_stage_delay_ms: int
    database_url: str | None
    storage_backend: str
    s3_bucket: str | None
    s3_region: str | None
    ocr_backend: str
    llm_backend: str
    gemini_api_key: str | None
    gemini_model: str
    llm_timeout_seconds: int
    llm_max_retries: int
    ocr_lang: str
    extraction_llm_enabled: bool
    extraction_mode: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv()

    env = os.getenv("SEDU_ENV", "development")
    cors = os.getenv("SEDU_CORS_ORIGINS", "http://localhost:3000")
    upload_dir = Path(os.getenv("SEDU_UPLOAD_DIR", "backend/uploads"))
    job_stage_delay_ms = _parse_non_negative_int(os.getenv("SEDU_JOB_STAGE_DELAY_MS"), default=0)
    storage_backend = os.getenv("SEDU_STORAGE_BACKEND", "local").lower()
    ocr_backend = os.getenv("SEDU_OCR_BACKEND", "mock").lower()
    llm_backend = os.getenv("SEDU_LLM_BACKEND", "mock").lower()
    llm_timeout_seconds = _parse_non_negative_int(os.getenv("SEDU_LLM_TIMEOUT_SECONDS"), default=90) or 90
    llm_max_retries = _parse_non_negative_int(os.getenv("SEDU_LLM_MAX_RETRIES"), default=1)
    ocr_lang = os.getenv("SEDU_OCR_LANG", "kor+eng").strip() or "kor+eng"
    extraction_llm_enabled = _parse_bool(os.getenv("SEDU_EXTRACTION_LLM_ENABLED"), default=True)
    extraction_mode = os.getenv("SEDU_EXTRACTION_MODE", "hybrid").strip().lower() or "hybrid"

    return Settings(
        env=env,
        app_name="SEDU API v2",
        cors_origins=_split_csv(cors),
        upload_dir=upload_dir,
        job_stage_delay_ms=job_stage_delay_ms,
        database_url=os.getenv("DATABASE_URL") or None,
        storage_backend=storage_backend,
        s3_bucket=os.getenv("SEDU_S3_BUCKET") or None,
        s3_region=os.getenv("SEDU_S3_REGION") or None,
        ocr_backend=ocr_backend,
        llm_backend=llm_backend,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        llm_timeout_seconds=llm_timeout_seconds,
        llm_max_retries=llm_max_retries,
        ocr_lang=ocr_lang,
        extraction_llm_enabled=extraction_llm_enabled,
        extraction_mode=extraction_mode,
    )

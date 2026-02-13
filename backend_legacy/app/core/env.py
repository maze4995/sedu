"""Environment loading helpers."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_backend_env() -> Path:
    """Load backend/.env once if python-dotenv is available."""
    env_path = Path(__file__).resolve().parents[2] / ".env"

    try:
        from dotenv import load_dotenv
    except ImportError:
        logger.debug("python-dotenv not installed; skipping .env load")
        return env_path

    load_dotenv(dotenv_path=env_path, override=False)
    return env_path

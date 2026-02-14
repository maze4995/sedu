import os
import sys
from pathlib import Path


# Keep tests deterministic and local-only.
os.environ["SEDU_SKIP_DOTENV"] = "1"
os.environ["SEDU_STORAGE_BACKEND"] = "local"
os.environ["SEDU_UPLOAD_DIR"] = "backend/test_uploads"
os.environ["SEDU_OCR_BACKEND"] = "mock"
os.environ["SEDU_LLM_BACKEND"] = "mock"
os.environ["SEDU_EXTRACTION_MODE"] = "hybrid"
os.environ["SEDU_LLM_TIMEOUT_SECONDS"] = "5"
os.environ["SEDU_LLM_MAX_RETRIES"] = "0"
os.environ["GEMINI_API_KEY"] = ""
os.environ["SEDU_SYNC_PROCESSING"] = "1"

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = BACKEND_ROOT / "test_sedu_v2.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

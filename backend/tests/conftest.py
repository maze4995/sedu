import os
import sys
from pathlib import Path


# Keep tests deterministic and local-only.
os.environ.setdefault("SEDU_STORAGE_BACKEND", "local")
os.environ.setdefault("SEDU_UPLOAD_DIR", "backend/test_uploads")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = BACKEND_ROOT / "test_sedu_v2.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB_PATH}")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

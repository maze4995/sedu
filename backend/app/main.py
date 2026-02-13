from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v2.router import router as v2_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.infra.db.session import init_db

settings = get_settings()
configure_logging(logging.INFO)
init_db()

app = FastAPI(title=settings.app_name, version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v2_router)

settings.upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")


@app.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    return {"ok": "true"}

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health
from app.api.v1 import extraction_jobs, questions, sets
from app import models as _models  # noqa: F401
from app.db.base import Base
from app.db.session import _get_engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Auto-create tables (safe no-op if they already exist).
    Base.metadata.create_all(bind=_get_engine())
    yield


app = FastAPI(title="SEDU API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sets.router)
app.include_router(extraction_jobs.router)
app.include_router(questions.router)

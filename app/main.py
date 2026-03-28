from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import ensure_database
from app.services.model_service import SentimentAnalyzer


@asynccontextmanager
async def lifespan(application: FastAPI):
    ensure_database(settings.database_path)
    application.state.database_path = settings.database_path
    application.state.analyzer = SentimentAnalyzer(
        settings.model_path,
        confidence_temperature=settings.confidence_temperature,
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="MiniLM tabanli LawBridge sentiment analysis backend servisi.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/analysis/health",
    }

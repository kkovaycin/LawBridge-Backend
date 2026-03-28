from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def _resolve_path(env_name: str, default_relative_path: str) -> Path:
    raw_value = os.getenv(env_name)
    candidate = Path(raw_value) if raw_value else BACKEND_DIR / default_relative_path
    if not candidate.is_absolute():
        candidate = BACKEND_DIR / candidate
    return candidate.resolve()


def _parse_origins(raw_value: str | None) -> list[str]:
    if not raw_value:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("LAWBRIDGE_APP_NAME", "LawBridge Sentiment API")
    api_v1_prefix: str = os.getenv("LAWBRIDGE_API_PREFIX", "/api/v1")
    model_path: Path = _resolve_path(
        "LAWBRIDGE_MODEL_PATH",
        "models/MiniLM_weak_summary_to_reasoning_seed42_ep7_msl256",
    )
    database_path: Path = _resolve_path("LAWBRIDGE_DATABASE_PATH", "data/lawbridge.db")
    cors_origins: list[str] = field(
        default_factory=lambda: _parse_origins(os.getenv("LAWBRIDGE_CORS_ORIGINS"))
    )
    confidence_temperature: float = float(os.getenv("LAWBRIDGE_CONFIDENCE_TEMPERATURE", "8.0"))


settings = Settings()

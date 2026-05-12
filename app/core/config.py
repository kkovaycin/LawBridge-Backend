from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    app_name: str = "LawBridge Backend"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    sentiment_model_path: Path = PROJECT_ROOT / "models" / "sentiment_berturk_model"
    intent_model_path: Path = PROJECT_ROOT / "models" / "intent_berturk_model"
    legal_model_path: Path = PROJECT_ROOT / "models" / "lawbridge_legal_model"
    reasoning_model_path: Path = PROJECT_ROOT / "models" / "MiniLM_weak_summary_to_reasoning_seed42_ep7_msl256"
    judgements_dataset_dir: Path = PROJECT_ROOT / "Structured_Judgements"

    model_device: str = Field(default="auto", pattern="^(auto|cpu|cuda)$")
    eager_load_models: bool = False
    max_sequence_length: int = Field(default=512, ge=64, le=4096)
    youtube_api_key: str | None = None
    youtube_max_comments: int = Field(default=25, ge=1, le=100)
    youtube_request_timeout_seconds: int = Field(default=15, ge=1, le=60)
    analysis_store_path: Path = PROJECT_ROOT / "data" / "analyses.json"

    @model_validator(mode="after")
    def resolve_project_paths(self) -> "Settings":
        for field_name in (
            "sentiment_model_path",
            "intent_model_path",
            "legal_model_path",
            "reasoning_model_path",
            "judgements_dataset_dir",
            "analysis_store_path",
        ):
            value = getattr(self, field_name)
            if not value.is_absolute():
                value = PROJECT_ROOT / value
            setattr(self, field_name, value.resolve())
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]

        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.models.schemas import ModelInfo
from app.services.classifiers import MultiLabelClassifier, read_labels_from_config
from app.services.model_sources import model_ref_available, model_ref_kind
from app.services.precedents import PrecedentService
from app.services.storage import build_analysis_store
from app.services.youtube import YouTubeCommentClient


class ModelRegistry:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        hf_token = settings.hf_token_value
        self.sentiment = MultiLabelClassifier(
            key="sentiment",
            model_path=settings.sentiment_model_path,
            device=settings.model_device,
            max_length=settings.max_sequence_length,
            hf_token=hf_token,
        )
        self.intent = MultiLabelClassifier(
            key="intent",
            model_path=settings.intent_model_path,
            device=settings.model_device,
            max_length=settings.max_sequence_length,
            hf_token=hf_token,
        )
        self.legal = MultiLabelClassifier(
            key="legal",
            model_path=settings.legal_model_path,
            device=settings.model_device,
            max_length=settings.max_sequence_length,
            hf_token=hf_token,
        )
        self.precedents = PrecedentService(
            model_path=settings.reasoning_model_path,
            dataset_dir=settings.judgements_dataset_dir,
            device=settings.model_device,
            hf_token=hf_token,
        )
        self.youtube = YouTubeCommentClient(
            api_key=settings.youtube_api_key,
            max_comments=settings.youtube_max_comments,
            timeout_seconds=settings.youtube_request_timeout_seconds,
        )
        self.store = build_analysis_store(
            database_url=settings.postgres_url,
            analysis_store_path=settings.analysis_store_path,
            auto_create_db_tables=settings.auto_create_db_tables,
        )

    def load_all(self) -> None:
        self.sentiment.predict("model warmup", top_k=1)
        self.intent.predict("model warmup", top_k=1)
        self.legal.predict("model warmup", top_k=1)
        self.precedents.search("model warmup", top_k=1)

    def loaded_status(self) -> dict[str, bool]:
        return {
            "sentiment": self.sentiment.loaded,
            "intent": self.intent.loaded,
            "legal": self.legal.loaded,
            "reasoning": self.precedents.loaded,
        }

    def available_status(self) -> dict[str, bool]:
        return {
            "sentiment": model_ref_available(self.settings.sentiment_model_path),
            "intent": model_ref_available(self.settings.intent_model_path),
            "legal": model_ref_available(self.settings.legal_model_path),
            "reasoning": model_ref_available(self.settings.reasoning_model_path),
        }

    def model_info(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                key="sentiment",
                path=str(self.settings.sentiment_model_path),
                available=model_ref_available(self.settings.sentiment_model_path),
                loaded=self.sentiment.loaded,
                labels=self.sentiment.labels
                or read_labels_from_config(self.settings.sentiment_model_path, hf_token=self.settings.hf_token_value),
                extra={"sourceType": model_ref_kind(self.settings.sentiment_model_path)},
            ),
            ModelInfo(
                key="intent",
                path=str(self.settings.intent_model_path),
                available=model_ref_available(self.settings.intent_model_path),
                loaded=self.intent.loaded,
                labels=self.intent.labels
                or read_labels_from_config(self.settings.intent_model_path, hf_token=self.settings.hf_token_value),
                extra={"sourceType": model_ref_kind(self.settings.intent_model_path)},
            ),
            ModelInfo(
                key="legal",
                path=str(self.settings.legal_model_path),
                available=model_ref_available(self.settings.legal_model_path),
                loaded=self.legal.loaded,
                labels=self.legal.labels
                or read_labels_from_config(self.settings.legal_model_path, hf_token=self.settings.hf_token_value),
                extra={"sourceType": model_ref_kind(self.settings.legal_model_path)},
            ),
            ModelInfo(
                key="reasoning",
                path=str(self.settings.reasoning_model_path),
                available=model_ref_available(self.settings.reasoning_model_path),
                loaded=self.precedents.loaded,
                labels=[],
                extra={
                    "type": "sentence-transformers semantic search",
                    "sourceType": model_ref_kind(self.settings.reasoning_model_path),
                    "datasetPath": str(self.settings.judgements_dataset_dir),
                    "datasetAvailable": self.settings.judgements_dataset_dir.exists(),
                    "precedentCount": self.precedents.count,
                    "youtubeCommentsConfigured": self.youtube.configured,
                    "youtubeMaxComments": self.settings.youtube_max_comments,
                },
            ),
        ]


@lru_cache
def get_model_registry() -> ModelRegistry:
    return ModelRegistry()

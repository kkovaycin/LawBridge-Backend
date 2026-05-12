from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.models.schemas import ModelInfo
from app.services.classifiers import MultiLabelClassifier, read_labels_from_config
from app.services.precedents import PrecedentService
from app.services.storage import AnalysisStore


class ModelRegistry:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.sentiment = MultiLabelClassifier(
            key="sentiment",
            model_path=settings.sentiment_model_path,
            device=settings.model_device,
            max_length=settings.max_sequence_length,
        )
        self.intent = MultiLabelClassifier(
            key="intent",
            model_path=settings.intent_model_path,
            device=settings.model_device,
            max_length=settings.max_sequence_length,
        )
        self.legal = MultiLabelClassifier(
            key="legal",
            model_path=settings.legal_model_path,
            device=settings.model_device,
            max_length=settings.max_sequence_length,
        )
        self.precedents = PrecedentService(
            model_path=settings.reasoning_model_path,
            dataset_dir=settings.judgements_dataset_dir,
            device=settings.model_device,
        )
        self.store = AnalysisStore(settings.analysis_store_path)

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
            "sentiment": self.settings.sentiment_model_path.exists(),
            "intent": self.settings.intent_model_path.exists(),
            "legal": self.settings.legal_model_path.exists(),
            "reasoning": self.settings.reasoning_model_path.exists(),
        }

    def model_info(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                key="sentiment",
                path=str(self.settings.sentiment_model_path),
                available=self.settings.sentiment_model_path.exists(),
                loaded=self.sentiment.loaded,
                labels=read_labels_from_config(self.settings.sentiment_model_path),
            ),
            ModelInfo(
                key="intent",
                path=str(self.settings.intent_model_path),
                available=self.settings.intent_model_path.exists(),
                loaded=self.intent.loaded,
                labels=read_labels_from_config(self.settings.intent_model_path),
            ),
            ModelInfo(
                key="legal",
                path=str(self.settings.legal_model_path),
                available=self.settings.legal_model_path.exists(),
                loaded=self.legal.loaded,
                labels=read_labels_from_config(self.settings.legal_model_path),
            ),
            ModelInfo(
                key="reasoning",
                path=str(self.settings.reasoning_model_path),
                available=self.settings.reasoning_model_path.exists(),
                loaded=self.precedents.loaded,
                labels=[],
                extra={
                    "type": "sentence-transformers semantic search",
                    "datasetPath": str(self.settings.judgements_dataset_dir),
                    "datasetAvailable": self.settings.judgements_dataset_dir.exists(),
                    "precedentCount": self.precedents.count,
                },
            ),
        ]


@lru_cache
def get_model_registry() -> ModelRegistry:
    return ModelRegistry()

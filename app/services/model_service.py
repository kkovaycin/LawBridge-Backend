from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from app.data.prototypes import SENTIMENT_DISPLAY, SENTIMENT_PROTOTYPES


@dataclass(frozen=True)
class AnalysisResult:
    sentiment: str
    sentiment_display: str
    confidence: float
    explanation: str
    matched_prototype: str
    scores: dict[str, float]
    model_name: str


class SentimentAnalyzer:
    def __init__(self, model_path: Path, *, confidence_temperature: float = 8.0) -> None:
        self.model_path = model_path
        self.confidence_temperature = confidence_temperature

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model path not found: {self.model_path}. Extract the provided model zip into backend/models "
                "or set LAWBRIDGE_MODEL_PATH in backend/.env."
            )

        self.model = SentenceTransformer(str(self.model_path))
        self.model_name = self.model_path.name
        self.prototype_embeddings = self._build_prototype_embeddings()

    @property
    def is_ready(self) -> bool:
        return True

    def _encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def _build_prototype_embeddings(self) -> dict[str, dict[str, object]]:
        prototype_index: dict[str, dict[str, object]] = {}
        for label, examples in SENTIMENT_PROTOTYPES.items():
            embeddings = self._encode(examples)
            centroid = embeddings.mean(axis=0)
            centroid /= np.linalg.norm(centroid)
            prototype_index[label] = {
                "examples": examples,
                "embeddings": embeddings,
                "centroid": centroid,
            }
        return prototype_index

    def analyze(self, text: str) -> AnalysisResult:
        text_embedding = self._encode([text])[0]
        similarities = {
            label: float(np.dot(text_embedding, prototype_data["centroid"]))
            for label, prototype_data in self.prototype_embeddings.items()
        }

        ordered_labels = ["negative", "neutral", "positive"]
        similarity_vector = np.array([similarities[label] for label in ordered_labels], dtype=np.float32)
        shifted = similarity_vector - np.max(similarity_vector)
        probabilities = np.exp(shifted * self.confidence_temperature)
        probabilities /= probabilities.sum()
        scores = {
            label: float(probability)
            for label, probability in zip(ordered_labels, probabilities.tolist(), strict=True)
        }

        sentiment = max(scores, key=scores.get)
        best_match_text, best_match_similarity = self._find_best_example(text_embedding, sentiment)
        explanation = (
            f"Metin, '{SENTIMENT_DISPLAY[sentiment]}' prototiplerine en yakin bulundu. "
            f"En yakin referans cumle: '{best_match_text}'. "
            f"Bu eslesmenin benzerlik skoru {best_match_similarity:.3f}."
        )

        return AnalysisResult(
            sentiment=sentiment,
            sentiment_display=SENTIMENT_DISPLAY[sentiment],
            confidence=round(scores[sentiment], 4),
            explanation=explanation,
            matched_prototype=best_match_text,
            scores={label: round(score, 4) for label, score in scores.items()},
            model_name=self.model_name,
        )

    def _find_best_example(self, text_embedding: np.ndarray, sentiment: str) -> tuple[str, float]:
        prototype_data = self.prototype_embeddings[sentiment]
        embeddings: np.ndarray = prototype_data["embeddings"]  # type: ignore[assignment]
        examples: list[str] = prototype_data["examples"]  # type: ignore[assignment]

        similarities = embeddings @ text_embedding
        best_index = int(np.argmax(similarities))
        return examples[best_index], float(similarities[best_index])

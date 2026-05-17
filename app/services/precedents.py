from __future__ import annotations

import re
from pathlib import Path
from threading import Lock

from app.data.judgements import load_judgement_dataset
from app.data.precedents import PRECEDENTS
from app.models.schemas import PrecedentMatch, PrecedentRecord, RiskLevel
from app.services.model_sources import (
    is_local_model_ref,
    model_ref_available,
    pretrained_model_source,
)


TURKISH_TRANSLATION = str.maketrans(
    {
        "\u00e7": "c",
        "\u011f": "g",
        "\u0131": "i",
        "i": "i",
        "\u00f6": "o",
        "\u015f": "s",
        "\u00fc": "u",
        "\u00c7": "c",
        "\u011e": "g",
        "I": "i",
        "\u0130": "i",
        "\u00d6": "o",
        "\u015e": "s",
        "\u00dc": "u",
    }
)


def normalize_text(value: str) -> str:
    return value.translate(TURKISH_TRANSLATION).casefold()


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", normalize_text(value)))


class PrecedentService:
    def __init__(
        self,
        model_path: str,
        dataset_dir: Path,
        device: str = "auto",
        hf_token: str | None = None,
    ) -> None:
        self.model_path = str(model_path).strip()
        self.dataset_dir = dataset_dir
        self.device_setting = device
        self.hf_token = hf_token
        self._model = None
        self._embeddings = None
        self._records: list[PrecedentRecord] | None = None
        self._corpus_by_id: dict[str, str] = {}
        self._lock = Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def records(self) -> list[PrecedentRecord]:
        if self._records is None:
            dataset = load_judgement_dataset(self.dataset_dir)
            if dataset.records:
                self._records = dataset.records
                self._corpus_by_id = dataset.corpus_by_id
            else:
                self._records = PRECEDENTS
                self._corpus_by_id = {
                    precedent.id: self._visible_precedent_text(precedent)
                    for precedent in PRECEDENTS
                }

        return self._records

    def list_precedents(
        self,
        query: str | None = None,
        risk_level: RiskLevel | None = None,
        saved: bool | None = None,
    ) -> list[PrecedentRecord]:
        records = self.records

        if risk_level is not None:
            records = [item for item in records if item.risk_level == risk_level]

        if saved is not None:
            records = [item for item in records if item.saved is saved]

        if query:
            query_tokens = tokenize(query)
            records = [
                item
                for item in records
                if query_tokens.intersection(tokenize(self._precedent_text(item)))
            ]

        return records

    def get_precedent(self, precedent_id: str) -> PrecedentRecord | None:
        return next((item for item in self.records if item.id == precedent_id), None)

    def search(self, text: str, top_k: int = 3) -> list[PrecedentMatch]:
        if model_ref_available(self.model_path):
            try:
                return self._semantic_search(text, top_k=top_k)
            except Exception:
                return self._keyword_search(text, top_k=top_k)

        return self._keyword_search(text, top_k=top_k)

    def _semantic_search(self, text: str, top_k: int) -> list[PrecedentMatch]:
        self._ensure_loaded()
        query_embedding = self._model.encode([text], normalize_embeddings=True)[0]

        scored: list[tuple[PrecedentRecord, float]] = []
        for precedent, embedding in zip(self.records, self._embeddings, strict=True):
            score = float(sum(query_embedding * embedding))
            scored.append((precedent, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            PrecedentMatch(
                precedent=precedent,
                score=round(max(0.0, min(1.0, score)), 6),
                reason="SentenceTransformer semantik benzerlik skoru",
            )
            for precedent, score in scored[:top_k]
        ]

    def _keyword_search(self, text: str, top_k: int) -> list[PrecedentMatch]:
        query_tokens = tokenize(text)
        scored: list[tuple[PrecedentRecord, float]] = []

        for precedent in self.records:
            precedent_tokens = tokenize(self._precedent_text(precedent))
            intersection = query_tokens.intersection(precedent_tokens)
            union = query_tokens.union(precedent_tokens)
            score = len(intersection) / len(union) if union else 0.0
            tag_bonus = sum(0.08 for tag in precedent.tags if tokenize(tag).intersection(query_tokens))
            scored.append((precedent, min(1.0, score + tag_bonus)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            PrecedentMatch(
                precedent=precedent,
                score=round(score, 6),
                reason="Anahtar kelime benzerlik skoru",
            )
            for precedent, score in scored[:top_k]
        ]

    def _ensure_loaded(self) -> None:
        if self.loaded:
            return

        with self._lock:
            if self.loaded:
                return

            local_only = is_local_model_ref(self.model_path)
            source = pretrained_model_source(self.model_path)
            if local_only and not Path(source).exists():
                raise FileNotFoundError(f"Reasoning model path bulunamadi: {source}")

            from sentence_transformers import SentenceTransformer

            device = self._resolve_device()
            token_kwargs = {"token": self.hf_token} if self.hf_token else {}
            try:
                self._model = SentenceTransformer(source, device=device, **token_kwargs)
            except TypeError:
                if not self.hf_token:
                    raise
                self._model = SentenceTransformer(source, device=device, use_auth_token=self.hf_token)
            corpus = [self._precedent_text(precedent) for precedent in self.records]
            self._embeddings = self._model.encode(corpus, normalize_embeddings=True)

    def _resolve_device(self) -> str | None:
        if self.device_setting == "cpu":
            return "cpu"

        if self.device_setting == "cuda":
            return "cuda"

        return None

    def _precedent_text(self, precedent: PrecedentRecord) -> str:
        return self._corpus_by_id.get(precedent.id) or self._visible_precedent_text(precedent)

    @staticmethod
    def _visible_precedent_text(precedent: PrecedentRecord) -> str:
        return " ".join(
            [
                precedent.title,
                precedent.court,
                precedent.summary,
                " ".join(precedent.tags),
            ]
        )

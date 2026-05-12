from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from app.models.schemas import ClassificationResponse, LabelScore


class ModelLoadError(RuntimeError):
    pass


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_labels_from_config(model_path: Path) -> list[str]:
    config_path = model_path / "config.json"
    if not config_path.exists():
        return []

    config = _read_json(config_path)
    id2label = config.get("id2label", {})
    return [
        label
        for _, label in sorted(
            ((int(index), label) for index, label in id2label.items()),
            key=lambda item: item[0],
        )
    ]


class MultiLabelClassifier:
    def __init__(
        self,
        key: str,
        model_path: Path,
        device: str = "auto",
        max_length: int = 512,
        default_threshold: float = 0.5,
    ) -> None:
        self.key = key
        self.model_path = model_path
        self.device_setting = device
        self.max_length = max_length
        self.default_threshold = default_threshold
        self.labels = read_labels_from_config(model_path)
        self.thresholds = self._load_thresholds()
        self._tokenizer = None
        self._model = None
        self._device = None
        self._lock = Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def predict(
        self,
        text: str,
        threshold: float | None = None,
        top_k: int = 5,
    ) -> ClassificationResponse:
        self._ensure_loaded()

        import torch

        inputs = self._tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        inputs = {key: value.to(self._device) for key, value in inputs.items()}

        with torch.no_grad():
            logits = self._model(**inputs).logits[0]
            scores = torch.sigmoid(logits).detach().cpu().tolist()

        scored = []
        for index, score in enumerate(scores):
            label = self._label_for_index(index)
            label_threshold = threshold if threshold is not None else self.thresholds.get(label, self.default_threshold)
            scored.append(
                LabelScore(
                    label=label,
                    score=round(float(score), 6),
                    threshold=round(float(label_threshold), 6),
                    passed_threshold=score >= label_threshold,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        visible = scored[:top_k]
        primary = scored[0]

        return ClassificationResponse(
            model_key=self.key,
            model_path=str(self.model_path),
            primary_label=primary.label,
            primary_score=primary.score,
            labels=visible,
        )

    def _ensure_loaded(self) -> None:
        if self.loaded:
            return

        with self._lock:
            if self.loaded:
                return

            if not self.model_path.exists():
                raise ModelLoadError(f"{self.key} model path bulunamadı: {self.model_path}")

            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            device_name = self._resolve_device(torch)
            self._device = torch.device(device_name)
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_path,
                local_files_only=True,
                use_fast=True,
            )
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_path,
                local_files_only=True,
            )
            self._model.to(self._device)
            self._model.eval()

            if not self.labels:
                config = getattr(self._model, "config", None)
                id2label = getattr(config, "id2label", {}) if config else {}
                self.labels = [
                    label
                    for _, label in sorted(id2label.items(), key=lambda item: int(item[0]))
                ]

    def _resolve_device(self, torch_module: Any) -> str:
        if self.device_setting == "cuda":
            if not torch_module.cuda.is_available():
                raise ModelLoadError("MODEL_DEVICE=cuda seçildi ancak CUDA kullanılamıyor")
            return "cuda"

        if self.device_setting == "auto" and torch_module.cuda.is_available():
            return "cuda"

        return "cpu"

    def _load_thresholds(self) -> dict[str, float]:
        threshold_path = self.model_path / "thresholds.json"
        if not threshold_path.exists():
            return {}

        raw = _read_json(threshold_path)
        return {
            str(label): float(value)
            for label, value in raw.items()
            if isinstance(value, int | float)
        }

    def _label_for_index(self, index: int) -> str:
        if index < len(self.labels):
            return self.labels[index]
        return f"LABEL_{index}"

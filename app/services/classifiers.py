from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from app.models.schemas import ClassificationResponse, LabelScore
from app.services.model_sources import (
    is_local_model_ref,
    pretrained_model_source,
    resolve_local_model_path,
)


class ModelLoadError(RuntimeError):
    pass


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _labels_from_id2label(id2label: Any) -> list[str]:
    if not isinstance(id2label, dict):
        return []

    labels: list[tuple[int, str]] = []
    for index, label in id2label.items():
        try:
            labels.append((int(index), str(label)))
        except (TypeError, ValueError):
            continue

    return [label for _, label in sorted(labels, key=lambda item: item[0])]


def read_labels_from_config(
    model_ref: str,
    hf_token: str | None = None,
    *,
    fetch_remote: bool = False,
) -> list[str]:
    if is_local_model_ref(model_ref):
        config_path = resolve_local_model_path(model_ref) / "config.json"
        if not config_path.exists():
            return []

        config = _read_json(config_path)
        return _labels_from_id2label(config.get("id2label", {}))

    if not fetch_remote:
        return []

    try:
        from transformers import AutoConfig

        config = AutoConfig.from_pretrained(model_ref, token=hf_token)
    except Exception:
        return []

    return _labels_from_id2label(getattr(config, "id2label", {}))


class MultiLabelClassifier:
    def __init__(
        self,
        key: str,
        model_path: str,
        device: str = "auto",
        max_length: int = 512,
        default_threshold: float = 0.5,
        hf_token: str | None = None,
    ) -> None:
        self.key = key
        self.model_path = str(model_path).strip()
        self.device_setting = device
        self.max_length = max_length
        self.default_threshold = default_threshold
        self.hf_token = hf_token
        self.labels = read_labels_from_config(self.model_path, hf_token=hf_token)
        self.thresholds: dict[str, float] = {}
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

            local_only = is_local_model_ref(self.model_path)
            source = pretrained_model_source(self.model_path)
            if local_only and not Path(source).exists():
                raise ModelLoadError(f"{self.key} model path bulunamadi: {source}")

            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                token_kwargs = {"token": self.hf_token} if self.hf_token else {}
                device_name = self._resolve_device(torch)
                self._device = torch.device(device_name)
                self._tokenizer = AutoTokenizer.from_pretrained(
                    source,
                    local_files_only=local_only,
                    use_fast=True,
                    **token_kwargs,
                )
                self._model = AutoModelForSequenceClassification.from_pretrained(
                    source,
                    local_files_only=local_only,
                    **token_kwargs,
                )
            except ModelLoadError:
                raise
            except Exception as exc:
                raise ModelLoadError(f"{self.key} modeli yuklenemedi ({source}): {exc}") from exc

            self._model.to(self._device)
            self._model.eval()
            self.thresholds = self._load_thresholds()

            if not self.labels:
                config = getattr(self._model, "config", None)
                id2label = getattr(config, "id2label", {}) if config else {}
                self.labels = _labels_from_id2label(id2label)

    def _resolve_device(self, torch_module: Any) -> str:
        if self.device_setting == "cuda":
            if not torch_module.cuda.is_available():
                raise ModelLoadError("MODEL_DEVICE=cuda secildi ancak CUDA kullanilamiyor")
            return "cuda"

        if self.device_setting == "auto" and torch_module.cuda.is_available():
            return "cuda"

        return "cpu"

    def _load_thresholds(self) -> dict[str, float]:
        if is_local_model_ref(self.model_path):
            threshold_path = resolve_local_model_path(self.model_path) / "thresholds.json"
        else:
            try:
                from huggingface_hub import hf_hub_download

                threshold_path = Path(
                    hf_hub_download(
                        repo_id=self.model_path,
                        filename="thresholds.json",
                        token=self.hf_token,
                    )
                )
            except Exception:
                return {}

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

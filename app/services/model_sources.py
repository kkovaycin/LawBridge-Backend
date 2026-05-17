from __future__ import annotations

from pathlib import Path

from app.core.config import PROJECT_ROOT


def _clean_model_ref(model_ref: str) -> str:
    return str(model_ref).strip()


def is_local_model_ref(model_ref: str) -> bool:
    raw = _clean_model_ref(model_ref)
    if not raw:
        return False

    normalized = raw.replace("\\", "/")
    path = Path(raw).expanduser()

    if path.is_absolute() or path.drive:
        return True

    if normalized in {"models", "model"}:
        return True

    if normalized.startswith(("models/", "model/", "./", "../", "~/")):
        return True

    if "\\" in raw:
        return True

    return (PROJECT_ROOT / path).exists()


def resolve_local_model_path(model_ref: str) -> Path:
    path = Path(_clean_model_ref(model_ref)).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def pretrained_model_source(model_ref: str) -> str:
    if is_local_model_ref(model_ref):
        return str(resolve_local_model_path(model_ref))
    return _clean_model_ref(model_ref)


def model_ref_available(model_ref: str) -> bool:
    if is_local_model_ref(model_ref):
        return resolve_local_model_path(model_ref).exists()
    return bool(_clean_model_ref(model_ref))


def model_ref_kind(model_ref: str) -> str:
    return "local" if is_local_model_ref(model_ref) else "huggingface"

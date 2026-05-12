from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.schemas import PrecedentRecord, RiskLevel


@dataclass(frozen=True)
class JudgementDataset:
    records: list[PrecedentRecord]
    corpus_by_id: dict[str, str]


def load_judgement_dataset(dataset_dir: Path) -> JudgementDataset:
    if not dataset_dir.exists():
        return JudgementDataset(records=[], corpus_by_id={})

    records: list[PrecedentRecord] = []
    corpus_by_id: dict[str, str] = {}

    for path in sorted(dataset_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            record, corpus_text = _record_from_payload(path, payload)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue

        records.append(record)
        corpus_by_id[record.id] = corpus_text

    return JudgementDataset(records=records, corpus_by_id=corpus_by_id)


def _record_from_payload(path: Path, payload: dict[str, Any]) -> tuple[PrecedentRecord, str]:
    meta = _dict_value(payload.get("meta_data"))
    segments = _dict_value(payload.get("rrl_segments"))
    features = _dict_value(payload.get("structural_features"))

    case_subject = _clean(meta.get("case_subject")) or "Hukuki uyuşmazlık"
    court = _clean(meta.get("court_name")) or "Bilinmeyen mahkeme"
    decision_date = _parse_date(_clean(meta.get("karar_tarihi")) or _clean(meta.get("dava_tarihi")))
    summary = (
        _clean(payload.get("summary_for_human"))
        or _clean(payload.get("summary_for_model"))
        or _clean(segments.get("reasoning_text"))
        or _clean(segments.get("facts_text"))
        or "Karar özeti bulunamadı."
    )
    laws = _string_list(features.get("mentioned_laws"))
    title = _build_title(case_subject, court, meta)
    tags = _build_tags(case_subject, laws, summary)
    risk_level = _infer_risk_level(" ".join([case_subject, summary, " ".join(tags)]))

    record = PrecedentRecord(
        id=_record_id(path),
        title=title,
        court=court,
        date=decision_date,
        summary=summary,
        tags=tags,
        risk_level=risk_level,
        saved=False,
    )

    corpus_text = " ".join(
        item
        for item in [
            title,
            court,
            case_subject,
            summary,
            _clean(payload.get("summary_for_model")),
            _clean(segments.get("facts_text")),
            _clean(segments.get("reasoning_text")),
            _clean(segments.get("verdict_text")),
            " ".join(laws),
        ]
        if item
    )

    return record, corpus_text


def _record_id(path: Path) -> str:
    stem = path.stem.removeprefix("vision_llm_processed_")
    return f"judgement-{stem.replace('_', '-')}"


def _build_title(case_subject: str, court: str, meta: dict[str, Any]) -> str:
    normalized_subject = case_subject.strip(" .")
    if normalized_subject and normalized_subject.lower() not in {"dava", "hukuki uyuşmazlık"}:
        return normalized_subject[:180]

    esas_no = _clean(meta.get("esas_no"))
    karar_no = _clean(meta.get("karar_no"))
    suffix = " ".join(part for part in [f"{esas_no} E." if esas_no else "", f"{karar_no} K." if karar_no else ""] if part)
    return f"{court} {suffix}".strip()[:180]


def _build_tags(case_subject: str, laws: list[str], summary: str) -> list[str]:
    primary = _classify_case_type(" ".join([case_subject, summary]))
    tags = [primary]

    for law in laws:
        cleaned = _clean(law)
        if cleaned and cleaned not in tags:
            tags.append(cleaned[:48])
        if len(tags) >= 4:
            break

    return tags


def _classify_case_type(text: str) -> str:
    normalized = _normalize(text)
    keyword_map = [
        ("Hakaret / Tehdit", ["hakaret", "tehdit", "asagilama"]),
        ("Dolandırıcılık", ["dolandiricilik", "sahte kampanya"]),
        ("Kişilik hakkı", ["kisilik", "manevi tazminat", "itibar", "ozel hayat"]),
        ("Veri ihlali", ["kvkk", "veri ihlali", "kisisel veri"]),
        ("Taciz", ["taciz", "israrli takip"]),
        ("Marka / fikri hak", ["marka", "telif", "tasarim", "fikri", "sinai"]),
        ("Tüketici", ["tuketici", "ayipli"]),
        ("İtirazın iptali", ["itirazin iptali"]),
        ("İcra", ["icra", "takip", "haciz"]),
        ("Alacak", ["alacak", "bedel", "fatura", "ucret"]),
        ("Tazminat", ["tazminat", "zarar"]),
        ("İş hukuku", ["is mahkemesi", "isci", "kidem"]),
        ("Kira", ["kira", "tahliye", "kiralanan"]),
        ("Aile hukuku", ["bosanma", "nafaka", "velayet"]),
        ("Ticari uyuşmazlık", ["ticaret", "ticari", "sirket"]),
        ("Ceza", ["ceza", "sanik", "suc"]),
    ]

    for label, keywords in keyword_map:
        if any(keyword in normalized for keyword in keywords):
            return label

    return "Genel hukuk"


def _infer_risk_level(text: str) -> RiskLevel:
    normalized = _normalize(text)
    high_keywords = [
        "hakaret",
        "tehdit",
        "dolandiricilik",
        "taciz",
        "nefret",
        "kvkk",
        "veri ihlali",
        "kisisel veri",
    ]
    medium_keywords = [
        "tazminat",
        "kisilik",
        "itibar",
        "marka",
        "telif",
        "icra",
        "alacak",
    ]

    if any(keyword in normalized for keyword in high_keywords):
        return RiskLevel.high

    if any(keyword in normalized for keyword in medium_keywords):
        return RiskLevel.medium

    return RiskLevel.low


def _parse_date(value: str) -> str:
    for date_format in ("%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue

    return "1970-01-01"


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    return [_clean(item) for item in value if _clean(item)]


def _normalize(value: str) -> str:
    translation = str.maketrans(
        {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
            "Ç": "c",
            "Ğ": "g",
            "I": "i",
            "İ": "i",
            "Ö": "o",
            "Ş": "s",
            "Ü": "u",
        }
    )
    return value.translate(translation).casefold()

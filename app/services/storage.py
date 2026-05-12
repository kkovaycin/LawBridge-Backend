from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from app.models.schemas import AnalysisRecord, AnalysisResponse


class AnalysisStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()

    def list(self) -> list[AnalysisRecord]:
        raw_items = self._read()
        records = [AnalysisRecord.model_validate(item["record"]) for item in raw_items]
        return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get(self, analysis_id: str) -> AnalysisResponse | None:
        for item in self._read():
            if item.get("analysis", {}).get("id") == analysis_id:
                return AnalysisResponse.model_validate(item["analysis"])
        return None

    def save(self, analysis: AnalysisResponse) -> None:
        with self._lock:
            items = self._read()
            items = [
                item
                for item in items
                if item.get("analysis", {}).get("id") != analysis.id
            ]
            items.append(
                {
                    "record": self._record_from_analysis(analysis).model_dump(mode="json", by_alias=True),
                    "analysis": analysis.model_dump(mode="json", by_alias=True),
                }
            )
            self._write(items)

    def delete(self, analysis_id: str) -> bool:
        with self._lock:
            items = self._read()
            next_items = [
                item
                for item in items
                if item.get("analysis", {}).get("id") != analysis_id
            ]
            if len(next_items) == len(items):
                return False
            self._write(next_items)
            return True

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []

        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            return []

        return data

    def _write(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)

    @staticmethod
    def _record_from_analysis(analysis: AnalysisResponse) -> AnalysisRecord:
        return AnalysisRecord(
            id=analysis.id,
            title=analysis.title,
            preview_text=analysis.summary[:180],
            input_text=analysis.input_text,
            risk_level=analysis.risk_level,
            risk_label=analysis.risk_label,
            source_type=analysis.source_type,
            analyze_source_type=analysis.analyze_source_type,
            analysis_type=analysis.analysis_type,
            created_at=analysis.created_at,
        )

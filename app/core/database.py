from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def ensure_database(database_path: Path) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sentiment_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                sentiment TEXT NOT NULL,
                sentiment_display TEXT NOT NULL,
                confidence REAL NOT NULL,
                negative_score REAL NOT NULL,
                neutral_score REAL NOT NULL,
                positive_score REAL NOT NULL,
                explanation TEXT NOT NULL,
                matched_prototype TEXT NOT NULL,
                model_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def insert_analysis_record(
    database_path: Path,
    *,
    text: str,
    sentiment: str,
    confidence: float,
    negative_score: float,
    neutral_score: float,
    positive_score: float,
    explanation: str,
    matched_prototype: str,
    model_name: str,
) -> tuple[int, str]:
    created_at = datetime.now(timezone.utc).isoformat()
    sentiment_display = {
        "positive": "Olumlu",
        "neutral": "Notr",
        "negative": "Olumsuz",
    }[sentiment]

    with sqlite3.connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO sentiment_analyses (
                text,
                sentiment,
                sentiment_display,
                confidence,
                negative_score,
                neutral_score,
                positive_score,
                explanation,
                matched_prototype,
                model_name,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                text,
                sentiment,
                sentiment_display,
                confidence,
                negative_score,
                neutral_score,
                positive_score,
                explanation,
                matched_prototype,
                model_name,
                created_at,
            ),
        )
        connection.commit()
        return cursor.lastrowid, created_at


def fetch_recent_analyses(database_path: Path, limit: int = 10) -> list[dict[str, object]]:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT
                id,
                text,
                sentiment,
                sentiment_display,
                confidence,
                negative_score,
                neutral_score,
                positive_score,
                explanation,
                matched_prototype,
                model_name,
                created_at
            FROM sentiment_analyses
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]

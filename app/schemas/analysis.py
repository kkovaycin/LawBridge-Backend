from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SentimentAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=5000, description="User comment to analyse.")

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Text must contain at least 3 non-space characters.")
        return cleaned


class SentimentScores(BaseModel):
    negative: float
    neutral: float
    positive: float


class SentimentAnalysisResponse(BaseModel):
    id: int
    text: str
    sentiment: Literal["negative", "neutral", "positive"]
    sentiment_display: str
    confidence: float
    explanation: str
    matched_prototype: str
    scores: SentimentScores
    created_at: str
    model_name: str


class AnalysisHistoryResponse(BaseModel):
    items: list[SentimentAnalysisResponse]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_path: str
    database_path: str
    api_prefix: str

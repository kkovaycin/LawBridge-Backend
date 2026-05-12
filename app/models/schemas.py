from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class APIModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


class AnalyzeSourceType(str, Enum):
    text_comment = "text-comment"
    social_media_link = "social-media-link"
    youtube_comment = "youtube-comment"
    document_text = "document-text"


class AnalysisType(str, Enum):
    insult_threat = "insult-threat"
    fraud = "fraud"
    personal_rights = "personal-rights"
    general_risk = "general-risk"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TextRequest(APIModel):
    text: str = Field(..., min_length=1, max_length=20000)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text boş olamaz")
        return stripped


class AnalyzeRequest(APIModel):
    text: str = Field(..., min_length=1, max_length=20000)
    source_type: AnalyzeSourceType = AnalyzeSourceType.text_comment
    analysis_type: AnalysisType | None = None
    save: bool = True
    context: str | None = Field(default=None, max_length=4000)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text boş olamaz")
        return stripped

    @field_validator("context")
    @classmethod
    def strip_context(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class LabelScore(APIModel):
    label: str
    score: float
    threshold: float
    passed_threshold: bool


class ClassificationResponse(APIModel):
    model_key: str
    model_path: str
    primary_label: str
    primary_score: float
    labels: list[LabelScore]


class Classifications(APIModel):
    sentiment: ClassificationResponse
    intent: ClassificationResponse
    legal: ClassificationResponse


class ActionLink(APIModel):
    href: str
    label: str
    variant: str = Field(pattern="^(primary|secondary)$")


class YouTubeCommentAnalysis(APIModel):
    id: str
    author: str | None = None
    text: str
    published_at: str | None = None
    like_count: int = 0
    risk_level: RiskLevel
    risk_label: str
    legal_topic: str
    analysis_type: AnalysisType
    primary_legal_label: str
    primary_legal_score: float


class YouTubeAnalysisStats(APIModel):
    video_id: str
    comment_count: int
    flagged_count: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    analyzed_comment_limit: int


class AnalysisCardResult(APIModel):
    risk_level: str
    legal_topic: str
    summary: str
    recommended_actions: list[str]
    precedent_suggestion: str
    actions: list[ActionLink]
    youtube_stats: YouTubeAnalysisStats | None = None
    youtube_comments: list[YouTubeCommentAnalysis] = Field(default_factory=list)


class PrecedentRecord(APIModel):
    id: str
    title: str
    court: str
    date: str
    summary: str
    tags: list[str]
    risk_level: RiskLevel
    saved: bool = False


class PrecedentMatch(APIModel):
    precedent: PrecedentRecord
    score: float
    reason: str


class AnalysisRecord(APIModel):
    id: str
    title: str
    preview_text: str
    input_text: str
    risk_level: RiskLevel
    risk_label: str
    source_type: str
    analyze_source_type: AnalyzeSourceType
    analysis_type: AnalysisType
    created_at: datetime


class AnalysisResponse(APIModel):
    id: str
    title: str
    input_text: str
    source_type: str
    analyze_source_type: AnalyzeSourceType
    analysis_type: AnalysisType
    risk_level: RiskLevel
    risk_label: str
    legal_topic: str
    summary: str
    recommended_actions: list[str]
    precedent_suggestion: str
    precedent_matches: list[PrecedentMatch]
    classifications: Classifications
    result: AnalysisCardResult
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthResponse(APIModel):
    status: str
    service: str
    models_available: dict[str, bool]
    loaded_models: dict[str, bool]


class ModelInfo(APIModel):
    key: str
    path: str
    available: bool
    loaded: bool
    labels: list[str]
    extra: dict[str, Any] = Field(default_factory=dict)


class ModelsResponse(APIModel):
    models: list[ModelInfo]


class PrecedentSearchRequest(TextRequest):
    pass


class ApplicationDraftRequest(APIModel):
    text: str = Field(..., min_length=1, max_length=20000)
    legal_topic: str | None = Field(default=None, max_length=300)
    recipient: str = Field(default="İlgili Makama", max_length=200)
    applicant_name: str | None = Field(default=None, max_length=200)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text boş olamaz")
        return stripped


class ApplicationDraftResponse(APIModel):
    title: str
    draft: str
    warnings: list[str]

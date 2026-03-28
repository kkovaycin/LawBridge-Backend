from fastapi import APIRouter, Query, Request

from app.core.config import settings
from app.core.database import fetch_recent_analyses, insert_analysis_record
from app.schemas.analysis import AnalysisHistoryResponse, HealthResponse, SentimentAnalysisRequest, SentimentAnalysisResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/sentiment", response_model=SentimentAnalysisResponse)
def analyze_sentiment(payload: SentimentAnalysisRequest, request: Request) -> SentimentAnalysisResponse:
    analyzer = request.app.state.analyzer
    result = analyzer.analyze(payload.text)

    record_id, created_at = insert_analysis_record(
        database_path=request.app.state.database_path,
        text=payload.text,
        sentiment=result.sentiment,
        confidence=result.confidence,
        negative_score=result.scores["negative"],
        neutral_score=result.scores["neutral"],
        positive_score=result.scores["positive"],
        explanation=result.explanation,
        matched_prototype=result.matched_prototype,
        model_name=result.model_name,
    )

    return SentimentAnalysisResponse(
        id=record_id,
        text=payload.text,
        sentiment=result.sentiment,
        sentiment_display=result.sentiment_display,
        confidence=result.confidence,
        explanation=result.explanation,
        matched_prototype=result.matched_prototype,
        scores=result.scores,
        created_at=created_at,
        model_name=result.model_name,
    )


@router.get("/history", response_model=AnalysisHistoryResponse)
def get_history(request: Request, limit: int = Query(default=10, ge=1, le=100)) -> AnalysisHistoryResponse:
    rows = fetch_recent_analyses(request.app.state.database_path, limit=limit)
    items = [
        SentimentAnalysisResponse(
            id=row["id"],
            text=row["text"],
            sentiment=row["sentiment"],
            sentiment_display=row["sentiment_display"],
            confidence=row["confidence"],
            explanation=row["explanation"],
            matched_prototype=row["matched_prototype"],
            scores={
                "negative": row["negative_score"],
                "neutral": row["neutral_score"],
                "positive": row["positive_score"],
            },
            created_at=row["created_at"],
            model_name=row["model_name"],
        )
        for row in rows
    ]
    return AnalysisHistoryResponse(items=items)


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    analyzer = request.app.state.analyzer
    return HealthResponse(
        status="ok",
        model_loaded=analyzer.is_ready,
        model_path=str(analyzer.model_path),
        database_path=str(request.app.state.database_path),
        api_prefix=settings.api_v1_prefix,
    )

from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import get_settings
from app.models.schemas import (
    AnalysisRecord,
    AnalysisResponse,
    AnalyzeRequest,
    ApplicationDraftRequest,
    ApplicationDraftResponse,
    ClassificationResponse,
    HealthResponse,
    ModelsResponse,
    PrecedentMatch,
    PrecedentRecord,
    PrecedentSearchRequest,
    RiskLevel,
    TextRequest,
)
from app.services.analysis import AnalysisService
from app.services.applications import create_application_draft
from app.services.classifiers import ModelLoadError
from app.services.registry import get_model_registry


router = APIRouter()


def registry():
    return get_model_registry()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    current_registry = registry()
    return HealthResponse(
        status="ok",
        service=get_settings().app_name,
        models_available=current_registry.available_status(),
        loaded_models=current_registry.loaded_status(),
    )


@router.get("/models", response_model=ModelsResponse, tags=["system"])
def models() -> ModelsResponse:
    return ModelsResponse(models=registry().model_info())


@router.post("/analyze", response_model=AnalysisResponse, tags=["analysis"])
def analyze(request: AnalyzeRequest) -> AnalysisResponse:
    try:
        response = AnalysisService(registry()).analyze(request)
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    if request.save:
        registry().store.save(response)

    return response


@router.get("/analyses", response_model=list[AnalysisRecord], tags=["analysis"])
def list_analyses() -> list[AnalysisRecord]:
    return registry().store.list()


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse, tags=["analysis"])
def get_analysis(analysis_id: str) -> AnalysisResponse:
    analysis = registry().store.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analiz bulunamadı")
    return analysis


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["analysis"])
def delete_analysis(analysis_id: str) -> None:
    deleted = registry().store.delete(analysis_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analiz bulunamadı")


@router.post("/classify/sentiment", response_model=ClassificationResponse, tags=["classification"])
def classify_sentiment(request: TextRequest) -> ClassificationResponse:
    try:
        return registry().sentiment.predict(
            request.text,
            threshold=request.threshold,
            top_k=request.top_k,
        )
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/classify/intent", response_model=ClassificationResponse, tags=["classification"])
def classify_intent(request: TextRequest) -> ClassificationResponse:
    try:
        return registry().intent.predict(
            request.text,
            threshold=request.threshold,
            top_k=request.top_k,
        )
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.post("/classify/legal", response_model=ClassificationResponse, tags=["classification"])
def classify_legal(request: TextRequest) -> ClassificationResponse:
    try:
        return registry().legal.predict(
            request.text,
            threshold=request.threshold,
            top_k=request.top_k,
        )
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/precedents", response_model=list[PrecedentRecord], tags=["precedents"])
def list_precedents(
    query: str | None = Query(default=None, max_length=300),
    risk_level: RiskLevel | None = Query(default=None),
    saved: bool | None = Query(default=None),
) -> list[PrecedentRecord]:
    return registry().precedents.list_precedents(
        query=query,
        risk_level=risk_level,
        saved=saved,
    )


@router.get("/precedents/{precedent_id}", response_model=PrecedentRecord, tags=["precedents"])
def get_precedent(precedent_id: str) -> PrecedentRecord:
    precedent = registry().precedents.get_precedent(precedent_id)
    if precedent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emsal kaydı bulunamadı")
    return precedent


@router.post("/precedents/search", response_model=list[PrecedentMatch], tags=["precedents"])
def search_precedents(request: PrecedentSearchRequest) -> list[PrecedentMatch]:
    return registry().precedents.search(request.text, top_k=request.top_k)


@router.post("/applications/draft", response_model=ApplicationDraftResponse, tags=["applications"])
def create_draft(request: ApplicationDraftRequest) -> ApplicationDraftResponse:
    return create_application_draft(request)

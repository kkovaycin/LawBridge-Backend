from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

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
    PrecedentSaveRequest,
    PrecedentSearchRequest,
    RiskLevel,
    TextRequest,
    UserProfileRequest,
    UserProfileResponse,
)
from app.services.analysis import AnalysisService
from app.services.applications import create_application_draft
from app.services.classifiers import ModelLoadError
from app.services.registry import get_model_registry
from app.services.storage import RequestUser
from app.services.youtube import YouTubeCommentError


router = APIRouter()


def registry():
    return get_model_registry()


def current_user(
    x_lawbridge_user_id: str | None = Header(default=None),
    x_lawbridge_user_email: str | None = Header(default=None),
    x_lawbridge_user_name: str | None = Header(default=None),
    x_lawbridge_auth_provider: str | None = Header(default="firebase"),
) -> RequestUser:
    return RequestUser(
        id=_decode_header(x_lawbridge_user_id) or "anonymous",
        email=_decode_header(x_lawbridge_user_email),
        display_name=_decode_header(x_lawbridge_user_name),
        provider=_decode_header(x_lawbridge_auth_provider) or "firebase",
    )


def _decode_header(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return unquote(stripped) if stripped else None


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
def analyze(
    request: AnalyzeRequest,
    user: RequestUser = Depends(current_user),
) -> AnalysisResponse:
    try:
        response = AnalysisService(registry()).analyze(request)
    except ModelLoadError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except YouTubeCommentError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if request.save:
        registry().store.save(response, user=user)

    return response


@router.get("/analyses", response_model=list[AnalysisRecord], tags=["analysis"])
def list_analyses(user: RequestUser = Depends(current_user)) -> list[AnalysisRecord]:
    return registry().store.list(user=user)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse, tags=["analysis"])
def get_analysis(
    analysis_id: str,
    user: RequestUser = Depends(current_user),
) -> AnalysisResponse:
    analysis = registry().store.get(analysis_id, user=user)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analiz bulunamadı")
    return analysis


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["analysis"])
def delete_analysis(
    analysis_id: str,
    user: RequestUser = Depends(current_user),
) -> None:
    deleted = registry().store.delete(analysis_id, user=user)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analiz bulunamadı")


@router.get("/profile", response_model=UserProfileResponse, tags=["profile"])
def get_profile(user: RequestUser = Depends(current_user)) -> UserProfileResponse:
    return registry().store.get_profile(user=user)


@router.put("/profile", response_model=UserProfileResponse, tags=["profile"])
def update_profile(
    request: UserProfileRequest,
    user: RequestUser = Depends(current_user),
) -> UserProfileResponse:
    return registry().store.save_profile(request, user=user)


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


@router.get(
    "/precedents",
    response_model=list[PrecedentRecord],
    response_model_exclude_none=True,
    tags=["precedents"],
)
def list_precedents(
    query: str | None = Query(default=None, max_length=300),
    risk_level: RiskLevel | None = Query(default=None),
    saved: bool | None = Query(default=None),
    user: RequestUser = Depends(current_user),
) -> list[PrecedentRecord]:
    saved_ids = registry().store.saved_precedent_ids(user=user)
    return registry().precedents.list_precedents(
        query=query,
        risk_level=risk_level,
        saved=saved,
        saved_ids=saved_ids,
    )


@router.get(
    "/precedents/{precedent_id}",
    response_model=PrecedentRecord,
    response_model_exclude_none=True,
    tags=["precedents"],
)
def get_precedent(
    precedent_id: str,
    user: RequestUser = Depends(current_user),
) -> PrecedentRecord:
    saved_ids = registry().store.saved_precedent_ids(user=user)
    precedent = registry().precedents.get_precedent(
        precedent_id,
        saved_ids=saved_ids,
        include_full_text=True,
    )
    if precedent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emsal kaydı bulunamadı")
    return precedent


@router.put(
    "/precedents/{precedent_id}/saved",
    response_model=PrecedentRecord,
    response_model_exclude_none=True,
    tags=["precedents"],
)
def set_precedent_saved(
    precedent_id: str,
    request: PrecedentSaveRequest,
    user: RequestUser = Depends(current_user),
) -> PrecedentRecord:
    precedent = registry().precedents.get_precedent(precedent_id)
    if precedent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emsal kaydÄ± bulunamadÄ±")

    registry().store.set_precedent_saved(precedent_id, saved=request.saved, user=user)
    saved_ids = {precedent_id} if request.saved else set()
    updated_precedent = registry().precedents.get_precedent(
        precedent_id,
        saved_ids=saved_ids,
        include_full_text=True,
    )
    if updated_precedent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emsal kaydÄ± bulunamadÄ±")
    return updated_precedent


@router.post("/precedents/search", response_model=list[PrecedentMatch], tags=["precedents"])
def search_precedents(request: PrecedentSearchRequest) -> list[PrecedentMatch]:
    return registry().precedents.search(request.text, top_k=request.top_k)


@router.post("/applications/draft", response_model=ApplicationDraftResponse, tags=["applications"])
def create_draft(request: ApplicationDraftRequest) -> ApplicationDraftResponse:
    return create_application_draft(request)

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.registry import get_model_registry
from app.services.youtube import extract_youtube_video_id


client = TestClient(app)


def test_health_contract():
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert set(payload["modelsAvailable"]) == {"sentiment", "intent", "legal", "reasoning"}


def test_models_contract_exposes_labels_without_loading_weights():
    response = client.get("/api/v1/models")

    assert response.status_code == 200
    payload = response.json()
    keys = {item["key"] for item in payload["models"]}
    assert keys == {"sentiment", "intent", "legal", "reasoning"}


def test_precedents_contract():
    response = client.get("/api/v1/precedents")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 1000
    assert {"id", "title", "court", "date", "summary", "tags", "riskLevel", "saved"}.issubset(payload[0])
    assert payload[0]["id"].startswith("judgement-")


def test_extract_youtube_video_id_from_common_urls():
    assert extract_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://youtu.be/dQw4w9WgXcQ?t=42") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_video_id("not a youtube link") is None


def test_youtube_video_analysis_requires_api_key_before_loading_models(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    get_settings.cache_clear()
    get_model_registry.cache_clear()

    response = client.post(
        "/api/v1/analyze",
        json={
            "text": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "sourceType": "youtube-comment",
            "analysisType": "insult-threat",
            "save": False,
        },
    )

    assert response.status_code == 400
    assert "YOUTUBE_API_KEY" in response.json()["detail"]

    get_settings.cache_clear()
    get_model_registry.cache_clear()


def test_youtube_video_url_is_detected_from_text_comment_source(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "")
    get_settings.cache_clear()
    get_model_registry.cache_clear()

    response = client.post(
        "/api/v1/analyze",
        json={
            "text": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "sourceType": "text-comment",
            "analysisType": "insult-threat",
            "save": False,
        },
    )

    assert response.status_code == 400
    assert "YOUTUBE_API_KEY" in response.json()["detail"]

    get_settings.cache_clear()
    get_model_registry.cache_clear()

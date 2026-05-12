from fastapi.testclient import TestClient

from app.main import app


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

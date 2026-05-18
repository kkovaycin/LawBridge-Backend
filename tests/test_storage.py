from app.models.schemas import (
    AnalysisCardResult,
    AnalysisResponse,
    AnalysisType,
    ClassificationResponse,
    Classifications,
    LabelScore,
    RiskLevel,
    UserProfileRequest,
)
from app.services.storage import FileAnalysisStore, RequestUser


def test_file_store_scopes_analyses_by_user(tmp_path):
    store = FileAnalysisStore(tmp_path / "analyses.json")
    alice = RequestUser(id="alice", email="alice@example.com", display_name="Alice")
    bob = RequestUser(id="bob", email="bob@example.com", display_name="Bob")

    analysis = _analysis("analysis-1")
    store.save(analysis, user=alice)

    assert [record.id for record in store.list(user=alice)] == ["analysis-1"]
    assert store.get("analysis-1", user=alice) == analysis
    assert store.list(user=bob) == []
    assert store.get("analysis-1", user=bob) is None
    assert store.delete("analysis-1", user=bob) is False
    assert store.delete("analysis-1", user=alice) is True


def test_file_store_persists_user_profile(tmp_path):
    store = FileAnalysisStore(tmp_path / "analyses.json")
    user = RequestUser(id="user-1", email="user@example.com", display_name="Firebase Name")

    saved = store.save_profile(
        UserProfileRequest(
            display_name="Profile Name",
            email="profile@example.com",
            phone="5551234567",
            city="Istanbul",
            bio="Short bio",
        ),
        user=user,
    )
    loaded = store.get_profile(user=user)

    assert saved == loaded
    assert loaded.id == "user-1"
    assert loaded.display_name == "Profile Name"
    assert loaded.email == "profile@example.com"
    assert loaded.phone == "5551234567"
    assert loaded.city == "Istanbul"
    assert loaded.bio == "Short bio"


def test_file_store_scopes_saved_precedents_by_user(tmp_path):
    store = FileAnalysisStore(tmp_path / "analyses.json")
    alice = RequestUser(id="alice")
    bob = RequestUser(id="bob")

    assert store.saved_precedent_ids(user=alice) == set()

    assert store.set_precedent_saved("judgement-1", saved=True, user=alice) is True
    assert store.saved_precedent_ids(user=alice) == {"judgement-1"}
    assert store.saved_precedent_ids(user=bob) == set()

    assert store.set_precedent_saved("judgement-1", saved=False, user=alice) is False
    assert store.saved_precedent_ids(user=alice) == set()


def _analysis(analysis_id: str) -> AnalysisResponse:
    classification = ClassificationResponse(
        model_key="sentiment",
        model_path="lawbridge/test-model",
        primary_label="low",
        primary_score=0.91,
        labels=[
            LabelScore(
                label="low",
                score=0.91,
                threshold=0.5,
                passed_threshold=True,
            )
        ],
    )

    return AnalysisResponse(
        id=analysis_id,
        title="Test analysis",
        input_text="Test input",
        source_type="text",
        analyze_source_type="text-comment",
        analysis_type=AnalysisType.general_risk,
        risk_level=RiskLevel.low,
        risk_label="Low",
        legal_topic="General",
        summary="No critical risk detected.",
        recommended_actions=["Archive"],
        precedent_suggestion="No precedent required.",
        precedent_matches=[],
        classifications=Classifications(
            sentiment=classification,
            intent=classification,
            legal=classification,
        ),
        result=AnalysisCardResult(
            risk_level="low",
            legal_topic="General",
            summary="No critical risk detected.",
            recommended_actions=["Archive"],
            precedent_suggestion="No precedent required.",
            actions=[],
        ),
    )

"""Comprehensive tests for BYO-AI Provider Gateway, Consent Boundaries, and Provider Adapters."""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch
import urllib.error

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import (
    AICapability,
    AIResponse,
    ExecutionLocation,
    compute_prompt_hash,
    mask_secret,
)
from app.ai.providers.gateway import AIProviderGateway, get_ai_gateway
from app.ai.providers.gemini import GoogleGeminiProvider
from app.ai.providers.local import LocalExtractiveProvider
from app.ai.providers.openai_provider import OpenAICompatibleProvider, is_local_endpoint
from app.core.config import settings
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import AIConsent, AIRun, Transcript, TranscriptSegment, Video
from app.models.enums import ExecutionProfile, RootPolicy
from app.services.summary_service import answer_video_question, generate_video_summary


@pytest.fixture()
def db_session() -> Session:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSession()

    video = Video(
        filename="gateway_test.mp4",
        file_path="/tmp/gateway_test.mp4",
        file_hash="hash_gw_123",
        duration=120.0,
    )
    session.add(video)
    session.commit()

    transcript = Transcript(
        video_id=video.id,
        language="en",
        model_name="whisper-base",
        full_text="Artificial intelligence architecture requires clean abstractions and local-first privacy.",
    )
    session.add(transcript)
    session.commit()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        video_id=video.id,
        start_time=0.0,
        end_time=30.0,
        text="Artificial intelligence architecture requires clean abstractions and local-first privacy.",
        confidence=0.98,
    )
    session.add(seg)
    session.commit()

    from app.ai.providers.embeddings import index_video_chunks
    index_video_chunks(session, video.id)

    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# =========================================================================
# 1. Base Utilities & Secret Masking Tests
# =========================================================================

def test_mask_secret_masks_properly() -> None:
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    assert mask_secret("short") == "[REDACTED_SECRET]"
    assert mask_secret("sk-1234567890abcdef") == "sk-...cdef"
    assert "1234567890" not in mask_secret("sk-1234567890abcdef")


def test_compute_prompt_hash_is_deterministic() -> None:
    h1 = compute_prompt_hash("What is media intelligence?")
    h2 = compute_prompt_hash("What is media intelligence?")
    assert len(h1) == 64
    assert h1 == h2
    assert h1 != compute_prompt_hash("Different query")


# =========================================================================
# 2. Local Extractive Provider Tests
# =========================================================================

def test_local_provider_capabilities() -> None:
    local_prov = LocalExtractiveProvider()
    assert local_prov.is_available() is True
    assert local_prov.is_available(AICapability.LLM_QA) is True
    assert local_prov.is_available(AICapability.SUMMARIZATION) is True
    assert local_prov.execution_location == ExecutionLocation.LOCAL

    models = local_prov.list_models()
    assert len(models) >= 2
    model_ids = [m.model_id for m in models]
    assert "grounded-extractive-local" in model_ids
    assert "extractive-grounded-local" in model_ids

    # Text generation
    resp = local_prov.generate_text("Test prompt")
    assert resp.text == "Test prompt"
    assert resp.remote_egress is False
    assert resp.execution_location == ExecutionLocation.LOCAL

    # Structured JSON generation
    parsed, resp_json = local_prov.generate_structured_json(
        prompt="First sentence about technology. Second sentence about engineering. Third sentence about software."
    )
    assert "summary" in parsed
    assert "topics" in parsed
    assert "chapters" in parsed
    assert resp_json.remote_egress is False


# =========================================================================
# 3. Provider Adapters Endpoint & Credential Checks
# =========================================================================

def test_is_local_endpoint_detection() -> None:
    assert is_local_endpoint("http://localhost:11434/v1") is True
    assert is_local_endpoint("http://127.0.0.1:8000/v1") is True
    assert is_local_endpoint("https://api.openai.com/v1") is False
    assert is_local_endpoint("https://my-custom-server.internal:8080/v1") is False


def test_openai_provider_credential_validation() -> None:
    prov = OpenAICompatibleProvider()
    # Missing key for remote endpoint
    is_valid, err = prov.validate_credentials(api_key="", base_url="https://api.openai.com/v1")
    assert is_valid is False
    assert "API key is required" in str(err)

    # Mock successful remote validation
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        is_valid, err = prov.validate_credentials(api_key="sk-test-valid", base_url="https://api.openai.com/v1")
        assert is_valid is True
        assert err is None


def test_anthropic_provider_credential_validation() -> None:
    prov = AnthropicProvider()
    is_valid, err = prov.validate_credentials(api_key="")
    assert is_valid is False
    assert "API key is required" in str(err)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        is_valid, err = prov.validate_credentials(api_key="sk-ant-test-12345")
        assert is_valid is True
        assert err is None


def test_gemini_provider_credential_validation() -> None:
    prov = GoogleGeminiProvider()
    is_valid, err = prov.validate_credentials(api_key="")
    assert is_valid is False
    assert "API key is required" in str(err)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        is_valid, err = prov.validate_credentials(api_key="AIzaSyTestKey12345")
        assert is_valid is True
        assert err is None


# =========================================================================
# 4. Consent Evaluation Decision Matrix Tests
# =========================================================================

def test_consent_evaluation_rules(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    gateway = get_ai_gateway()
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)

    # 1. Local provider is always permitted
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="local",
        consent_remote_ai=False,
    )
    assert permitted is True
    assert source == "local_execution"

    # 2. Remote provider without consent is denied
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="google-gemini",
        consent_remote_ai=False,
    )
    assert permitted is False
    assert "No active consent" in str(source)

    # 3. Blocked by ExecutionProfile FULLY_OFFLINE_NO_AI
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="google-gemini",
        consent_remote_ai=True,
        execution_profile=ExecutionProfile.FULLY_OFFLINE_NO_AI,
    )
    assert permitted is False
    assert "Blocked by ExecutionProfile" in str(source)

    # 4. Blocked by ExecutionProfile LOCAL_AI
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=True,
        execution_profile=ExecutionProfile.LOCAL_AI,
    )
    assert permitted is False
    assert "Blocked by ExecutionProfile" in str(source)

    # 5. Blocked by RootPolicy LOCAL_ONLY
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=True,
        root_policy=RootPolicy.LOCAL_ONLY,
    )
    assert permitted is False
    assert "Blocked by RootPolicy" in str(source)

    # 6. Permitted by explicit request consent
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="google-gemini",
        consent_remote_ai=True,
    )
    assert permitted is True
    assert source == "request"

    # 7. Permitted by system admin setting
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", True)
    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="anthropic",
        consent_remote_ai=False,
    )
    assert permitted is True
    assert source == "admin_setting"
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)

    # 8. Permitted by active database consent
    consent = AIConsent(
        scope_type="library",
        scope_id="lib_123",
        provider="openai",
        endpoint_host="api.openai.com",
        data_categories='["query"]',
        capabilities='["llm_qa", "summarization"]',
        granted_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(consent)
    db_session.commit()

    permitted, source, consent_rec = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=False,
        scope_id="lib_123",
    )
    assert permitted is True
    assert source == "db_consent"
    assert consent_rec.id == consent.id

    # 9. Denied if database consent is revoked
    consent.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    permitted, source, _ = gateway.evaluate_consent(
        db=db_session,
        capability=AICapability.LLM_QA,
        provider_id="openai",
        consent_remote_ai=False,
        scope_id="lib_123",
    )
    assert permitted is False


# =========================================================================
# 5. Remote Provider Generation & Fallback Execution
# =========================================================================

def test_remote_generation_with_mock_openai(db_session: Session) -> None:
    gateway = get_ai_gateway()

    mock_resp_payload = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "OpenAI answer citing [00:10 - 00:20]."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(mock_resp_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        resp, consent_src = gateway.generate_llm_response(
            prompt="Analyze the video",
            capability=AICapability.LLM_QA,
            preferred_provider="openai",
            api_key="sk-test-openai-12345",
            consent_remote_ai=True,
            db=db_session,
            input_refs=["video:gw_123"],
        )
        assert resp.text == "OpenAI answer citing [00:10 - 00:20]."
        assert resp.provider == "openai"
        assert resp.remote_egress is True
        assert resp.prompt_tokens == 50
        assert resp.total_tokens == 65
        assert consent_src == "request"

        # Verify AIRun recorded in database
        run = db_session.query(AIRun).filter_by(provider="openai").first()
        assert run is not None
        assert run.model == "gpt-4o-mini"
        assert run.execution_location == "remote"
        assert len(run.prompt_hash) == 64


def test_remote_generation_fallback_on_network_failure(db_session: Session) -> None:
    gateway = get_ai_gateway()

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        resp, consent_src = gateway.generate_llm_response(
            prompt="Analyze the video text",
            capability=AICapability.LLM_QA,
            preferred_provider="openai",
            api_key="sk-test-fail-12345",
            consent_remote_ai=True,
            db=db_session,
        )
        # Should gracefully fallback to local provider
        assert resp.provider == "local"
        assert resp.remote_egress is False
        assert resp.execution_location == ExecutionLocation.LOCAL


# =========================================================================
# 6. REST API Endpoints Verification
# =========================================================================

def test_api_list_providers(client: TestClient) -> None:
    res = client.get("/api/v1/ai/providers")
    assert res.status_code == 200
    data = res.json()
    assert "providers" in data
    assert "models" in data
    prov_ids = [p["provider_id"] for p in data["providers"]]
    assert "local" in prov_ids
    assert "google-gemini" in prov_ids
    assert "openai" in prov_ids
    assert "anthropic" in prov_ids


def test_api_verify_provider_endpoint(client: TestClient) -> None:
    # Verify local
    res = client.post("/api/v1/ai/providers/verify", json={"provider": "local"})
    assert res.status_code == 200
    assert res.json()["is_valid"] is True

    # Verify invalid provider
    res_bad = client.post("/api/v1/ai/providers/verify", json={"provider": "non-existent"})
    assert res_bad.status_code == 404

    # Verify remote without key
    res_nokey = client.post("/api/v1/ai/providers/verify", json={"provider": "openai", "api_key": ""})
    assert res_nokey.status_code == 200
    assert res_nokey.json()["is_valid"] is False


def test_api_consent_crud_lifecycle(client: TestClient) -> None:
    # 1. Grant consent
    create_payload = {
        "provider": "google-gemini",
        "scope_type": "library",
        "scope_id": "lib_test_001",
        "endpoint_host": "generativelanguage.googleapis.com",
        "data_categories": ["query", "transcript_snippets"],
        "capabilities": ["llm_qa"],
        "budget_limit": 5.0,
        "expires_in_hours": 24,
    }
    grant_res = client.post("/api/v1/ai/consents", json=create_payload)
    assert grant_res.status_code == 201
    consent_id = grant_res.json()["id"]
    assert grant_res.json()["is_active"] is True

    # 2. List consents
    list_res = client.get("/api/v1/ai/consents?provider=google-gemini")
    assert list_res.status_code == 200
    consents = list_res.json()
    assert len(consents) >= 1
    assert any(c["id"] == consent_id for c in consents)

    # 3. Revoke consent
    revoke_res = client.delete(f"/api/v1/ai/consents/{consent_id}")
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "revoked"

    # 4. List without revoked
    active_res = client.get("/api/v1/ai/consents?include_revoked=false")
    assert not any(c["id"] == consent_id for c in active_res.json())


# =========================================================================
# 7. Backward Compatibility Integration with summary_service
# =========================================================================

def test_summary_service_backward_compatibility(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_REMOTE_CONSENT", False)
    vid = db_session.query(Video).first()

    # answer_video_question offline local
    ans = answer_video_question(
        db=db_session,
        query="What is local-first privacy?",
        video_id=vid.id,
        consent_remote_ai=False,
    )
    assert ans["remote_egress"] is False
    assert ans["provider"] == "local"
    assert ans["model_name"] == "grounded-extractive-local"
    assert len(ans["citations"]) >= 1

    # generate_video_summary offline local
    summary = generate_video_summary(
        db=db_session,
        video_id=vid.id,
        consent_remote_ai=False,
    )
    assert summary.video_id == vid.id
    assert "extractive" in summary.model_name
    assert json.loads(summary.topics_json)
    assert json.loads(summary.chapters_json)


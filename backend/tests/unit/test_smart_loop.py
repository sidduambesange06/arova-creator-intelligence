"""Comprehensive tests for Shared Tool Execution Engine and Smart Loop."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.smart_loop import SmartLoop, get_smart_loop
from app.database.session import Base, get_db, init_db
from app.main import app
from app.models.entities import AIRun, Transcript, TranscriptSegment, Video
from app.services.tool_engine import (
    ToolDefinition,
    ToolExecutionEngine,
    ToolExecutionError,
    get_tool_engine,
)


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
        filename="smart_loop_test.mp4",
        file_path="/tmp/smart_loop_test.mp4",
        file_hash="hash_sl_123",
        duration=180.0,
    )
    session.add(video)
    session.commit()

    transcript = Transcript(
        video_id=video.id,
        language="en",
        model_name="whisper-base",
        full_text="Autonomous agents execute shared tools with precision, read-only boundaries, and evidence timecodes.",
    )
    session.add(transcript)
    session.commit()

    seg = TranscriptSegment(
        transcript_id=transcript.id,
        video_id=video.id,
        start_time=15.0,
        end_time=45.0,
        text="Autonomous agents execute shared tools with precision, read-only boundaries, and evidence timecodes.",
        confidence=0.99,
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
# 1. Tool Execution Engine Tests
# =========================================================================

def test_tool_engine_registration_and_schemas() -> None:
    engine = get_tool_engine()
    read_only_tools = engine.list_tools(include_mutating=False)
    all_tools = engine.list_tools(include_mutating=True)

    assert len(read_only_tools) >= 12
    assert len(all_tools) == len(read_only_tools) + 1  # Includes export_video_clip

    # Check export schemas for dialects
    openai_schemas = engine.export_schemas("openai")
    assert len(openai_schemas) == len(read_only_tools)
    assert openai_schemas[0]["type"] == "function"
    assert "name" in openai_schemas[0]["function"]

    gemini_schemas = engine.export_schemas("gemini")
    assert len(gemini_schemas) == len(read_only_tools)
    assert "parameters" in gemini_schemas[0]

    anthropic_schemas = engine.export_schemas("anthropic")
    assert len(anthropic_schemas) == len(read_only_tools)
    assert "input_schema" in anthropic_schemas[0]


def test_tool_engine_execution_and_gating(db_session: Session) -> None:
    engine = get_tool_engine()

    # 1. Execute read-only tool successfully
    res = engine.execute_tool("list_videos", {}, db=db_session)
    assert res["status"] == "success"
    assert len(res["result"]) >= 1

    # 2. Unknown tool raises ToolExecutionError
    with pytest.raises(ToolExecutionError):
        engine.execute_tool("non_existent_tool", {}, db=db_session)

    # 3. Mutating tool without explicit opt-in fails
    with pytest.raises(ToolExecutionError) as exc_info:
        engine.execute_tool("export_video_clip", {"video_id": "v1", "start_time": 0, "end_time": 10}, db=db_session, allow_mutating=False)
    assert "mutating operation" in str(exc_info.value)


# =========================================================================
# 2. Smart Loop Deterministic Offline Execution
# =========================================================================

def test_smart_loop_local_offline_execution(db_session: Session) -> None:
    loop = get_smart_loop()
    res = loop.run(
        query="What do autonomous agents execute?",
        db=db_session,
        consent_remote_ai=False,
    )

    assert res.provider == "local"
    assert res.execution_location == "local"
    assert res.remote_egress is False
    assert len(res.steps) >= 2
    assert len(res.citations) >= 1
    assert "Autonomous agents execute shared tools" in res.final_answer
    assert "[0:15 - 0:45]" in res.final_answer

    # Verify AIRun audit record created
    run = db_session.query(AIRun).filter_by(provider="local").first()
    assert run is not None
    assert run.model == "grounded-deterministic-planner"


# =========================================================================
# 3. Smart Loop Remote Multi-Turn Execution
# =========================================================================

def test_smart_loop_remote_multiturn_loop(db_session: Session) -> None:
    loop = get_smart_loop()

    # Simulate 2 turns: Turn 1 tool call, Turn 2 final answer
    call_turn_1 = json.dumps({
        "action": "tool_call",
        "tool": "get_evidence_citations",
        "arguments": {"query": "precision boundaries", "top_k": 3},
    })
    call_turn_2 = json.dumps({
        "action": "final_answer",
        "answer": "Agents execute with strict read-only boundaries citing [0:15 - 0:45].",
    })

    with patch("app.ai.providers.openai_provider.OpenAICompatibleProvider.generate_text") as mock_gen:
        mock_resp_1 = MagicMock()
        mock_resp_1.text = call_turn_1
        mock_resp_2 = MagicMock()
        mock_resp_2.text = call_turn_2
        mock_gen.side_effect = [mock_resp_1, mock_resp_2]

        res = loop.run(
            query="Explain agent boundaries",
            db=db_session,
            provider="openai",
            api_key="sk-test-loop-key",
            consent_remote_ai=True,
            max_turns=5,
        )

        assert res.provider == "openai"
        assert res.remote_egress is True
        assert res.total_turns == 2
        assert len(res.steps) == 1
        assert res.steps[0].tool_name == "get_evidence_citations"
        assert "read-only boundaries" in res.final_answer


# =========================================================================
# 4. REST API Endpoints Verification
# =========================================================================

def test_api_list_tools(client: TestClient) -> None:
    res = client.get("/api/v1/tools?dialect=openai")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 12
    assert len(data["schemas"]) >= 12
    tool_names = [t["name"] for t in data["tools"]]
    assert "list_videos" in tool_names
    assert "get_evidence_citations" in tool_names
    assert "export_video_clip" not in tool_names  # Gated by default


def test_api_execute_tool(client: TestClient) -> None:
    # 1. Execute read-only tool
    res = client.post("/api/v1/tools/execute", json={"tool": "get_capability_status", "arguments": {}})
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 2. Execute mutating tool without allow_mutating -> 403 Forbidden
    res_mut = client.post(
        "/api/v1/tools/execute",
        json={"tool": "export_video_clip", "arguments": {"video_id": "v1", "start_time": 0, "end_time": 5}},
    )
    assert res_mut.status_code == 403

    # 3. Unknown tool -> 404
    res_unknown = client.post("/api/v1/tools/execute", json={"tool": "unknown_tool", "arguments": {}})
    assert res_unknown.status_code == 404


def test_api_run_smart_loop(client: TestClient) -> None:
    payload = {
        "query": "What are agent boundaries?",
        "consent_remote_ai": False,
        "max_turns": 3,
    }
    res = client.post("/api/v1/agent/smart-loop", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "local"
    assert data["remote_egress"] is False
    assert len(data["steps"]) >= 2
    assert "final_answer" in data


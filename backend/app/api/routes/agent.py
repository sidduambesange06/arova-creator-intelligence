"""REST API routes for Shared Tools and Smart Loop Execution Engine.

Exposes canonical tool discovery, sandboxed tool dispatch,
and goal-directed multi-turn agentic reasoning over video media.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.smart_loop import get_smart_loop
from app.database.session import get_db
from app.services.tool_engine import ToolExecutionError, get_tool_engine

router = APIRouter(prefix="/api/v1", tags=["agent-smart-loop"])


class ExecuteToolRequest(BaseModel):
    tool: str = Field(..., description="Canonical tool name to execute")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool input arguments")
    allow_mutating: bool = Field(default=False, description="Explicit opt-in to allow mutating operations")


class SmartLoopRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Goal-directed query or instruction")
    video_id: str | None = Field(default=None, description="Optional video UUID filter")
    provider: str | None = Field(default=None, description="AI provider: local, google-gemini, openai, anthropic")
    model: str | None = Field(default=None, description="Target model identifier")
    api_key: str | None = None
    base_url: str | None = None
    consent_remote_ai: bool = False
    max_turns: int = Field(default=5, ge=1, le=10)


@router.get("/tools")
def list_available_tools(
    dialect: str = Query(default="openai", description="Tool schema dialect: openai, gemini, anthropic, or standard"),
    include_mutating: bool = Query(default=False, description="Whether to include mutating tools in the catalog"),
) -> dict[str, Any]:
    """List all registered shared media intelligence tools and schemas."""
    engine = get_tool_engine()
    tools = engine.list_tools(include_mutating=include_mutating)
    schemas = engine.export_schemas(dialect=dialect)
    return {
        "count": len(tools),
        "dialect": dialect,
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "is_read_only": t.is_read_only,
                "tags": t.tags,
            }
            for t in tools
        ],
        "schemas": schemas,
    }


@router.post("/tools/execute")
def execute_shared_tool(
    payload: ExecuteToolRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute a shared media tool with security boundaries and validation."""
    engine = get_tool_engine()
    try:
        return engine.execute_tool(
            name=payload.tool,
            arguments=payload.arguments,
            db=db,
            allow_mutating=payload.allow_mutating,
        )
    except ToolExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN if "mutating" in str(exc) else status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/agent/smart-loop")
def run_agent_smart_loop(
    payload: SmartLoopRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute the multi-turn Smart Loop agent over local media intelligence."""
    smart_loop = get_smart_loop()
    result = smart_loop.run(
        query=payload.query,
        db=db,
        video_id=payload.video_id,
        provider=payload.provider,
        model=payload.model,
        api_key=payload.api_key,
        base_url=payload.base_url,
        consent_remote_ai=payload.consent_remote_ai,
        max_turns=payload.max_turns,
    )

    return {
        "query": result.query,
        "final_answer": result.final_answer,
        "citations": result.citations,
        "steps": [
            {
                "turn": s.turn,
                "tool": s.tool_name,
                "arguments": s.arguments,
                "status": s.status,
                "result": s.result,
                "error": s.error,
            }
            for s in result.steps
        ],
        "total_turns": result.total_turns,
        "provider": result.provider,
        "model_name": result.model_name,
        "execution_location": result.execution_location,
        "remote_egress": result.remote_egress,
        "data_categories_egressed": result.data_categories_egressed,
        "consent_source": result.consent_source,
    }


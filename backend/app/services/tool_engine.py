"""Shared Tool Execution Engine for Arova Creator Intelligence.

Unifies tool definitions, argument schemas, safety gates, and dispatch
across FastMCP, REST API, internal SmartLoop, and SDK clients.
Enforces strict read-only boundaries by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import json
import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when a tool execution fails or violates safety boundaries."""
    pass


@dataclass
class ToolDefinition:
    """Canonical specification for an executable intelligence tool."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[..., Any]
    is_read_only: bool = True
    tags: list[str] = field(default_factory=list)


class ToolExecutionEngine:
    """Registry and execution dispatcher for shared tools."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        """Register a tool in the canonical registry."""
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> ToolDefinition:
        """Retrieve tool definition by name."""
        if name not in self._tools:
            raise ToolExecutionError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self, include_mutating: bool = False) -> list[ToolDefinition]:
        """List registered tools, filtering mutating tools by default."""
        return [
            t for t in self._tools.values()
            if t.is_read_only or include_mutating
        ]

    def export_schemas(self, dialect: str = "openai") -> list[dict[str, Any]]:
        """Export tool definitions formatted for target LLM function calling schema."""
        tools = self.list_tools(include_mutating=False)
        schemas = []
        for t in tools:
            if dialect == "openai":
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters_schema,
                    },
                })
            elif dialect == "gemini":
                schemas.append({
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema,
                })
            elif dialect == "anthropic":
                schemas.append({
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters_schema,
                })
            else:
                schemas.append({
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema,
                    "is_read_only": t.is_read_only,
                })
        return schemas

    def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        db: Session | None = None,
        allow_mutating: bool = False,
    ) -> dict[str, Any]:
        """Execute a tool with argument binding, security gating, and error boundary handling."""
        tool = self.get_tool(name)

        # Security boundary: Block mutating tools unless explicitly allowed
        if not tool.is_read_only and not allow_mutating:
            raise ToolExecutionError(
                f"Tool '{name}' is a mutating operation and is gated from automated execution."
            )

        # Inspect handler signature to bind arguments cleanly
        sig = inspect.signature(tool.handler)
        bound_kwargs: dict[str, Any] = {}
        for param_name, param in sig.parameters.items():
            if param_name in arguments:
                bound_kwargs[param_name] = arguments[param_name]
            elif param_name == "db":
                bound_kwargs["db"] = db
            elif param.default is not inspect.Parameter.empty:
                bound_kwargs[param_name] = param.default

        try:
            result = tool.handler(**bound_kwargs)
            return {
                "tool": name,
                "status": "success",
                "result": result,
            }
        except Exception as exc:
            logger.error("Tool '%s' execution failed: %s", name, exc, exc_info=True)
            return {
                "tool": name,
                "status": "error",
                "error": str(exc),
            }


# Global Tool Engine Singleton
_TOOL_ENGINE_INSTANCE: ToolExecutionEngine | None = None


def get_tool_engine() -> ToolExecutionEngine:
    """Access the global ToolExecutionEngine singleton with all standard tools registered."""
    global _TOOL_ENGINE_INSTANCE
    if _TOOL_ENGINE_INSTANCE is None:
        _TOOL_ENGINE_INSTANCE = ToolExecutionEngine()
        _register_standard_tools(_TOOL_ENGINE_INSTANCE)
    return _TOOL_ENGINE_INSTANCE


def _register_standard_tools(engine: ToolExecutionEngine) -> None:
    """Register all standard Arova media tools from video_tools into the engine."""
    from mcp_server.tools import video_tools

    engine.register_tool(
        ToolDefinition(
            name="list_videos",
            description="List indexed videos in the local media library with optional collection and status filters.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "collection_id": {"type": "string", "description": "Optional collection UUID filter"},
                    "status": {"type": "string", "description": "Processing status filter (e.g. completed, pending)"},
                },
            },
            handler=video_tools.list_videos,
            is_read_only=True,
            tags=["library", "inspection"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="get_video_metadata",
            description="Retrieve detailed technical metadata (resolution, duration, codecs, FPS) for a video.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "Video UUID"},
                },
                "required": ["video_id"],
            },
            handler=video_tools.get_video_metadata,
            is_read_only=True,
            tags=["metadata", "inspection"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="search_video_content",
            description="Search spoken dialogue, OCR text, and visual themes using two-stage hybrid RRF search.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "top_k": {"type": "integer", "description": "Number of top results to return", "default": 5},
                    "use_reranker": {"type": "boolean", "description": "Enable cross-encoder re-ranking", "default": True},
                },
                "required": ["query"],
            },
            handler=video_tools.search_video_content,
            is_read_only=True,
            tags=["search", "retrieval"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="search_transcripts",
            description="Search verbatim spoken words across video transcripts using lexical substring matching.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Spoken text search query"},
                    "video_id": {"type": "string", "description": "Optional video UUID filter"},
                },
                "required": ["query"],
            },
            handler=video_tools.search_transcripts,
            is_read_only=True,
            tags=["search", "transcripts"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="find_video_clips",
            description="Find optimal video clip candidates matching a query within duration constraints.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Theme or concept query"},
                    "min_duration": {"type": "number", "description": "Minimum duration in seconds", "default": 5.0},
                    "max_duration": {"type": "number", "description": "Maximum duration in seconds", "default": 60.0},
                },
                "required": ["query"],
            },
            handler=video_tools.find_video_clips,
            is_read_only=True,
            tags=["clips", "retrieval"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="summarize_video",
            description="Generate or retrieve a grounded factual summary with bullet points and key topics.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "Video UUID"},
                },
                "required": ["video_id"],
            },
            handler=video_tools.summarize_video,
            is_read_only=True,
            tags=["summary", "ai"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="get_video_chapters",
            description="Get structured chapter markers and timestamp intervals for navigating long-form video.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "Video UUID"},
                },
                "required": ["video_id"],
            },
            handler=video_tools.get_video_chapters,
            is_read_only=True,
            tags=["chapters", "navigation"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="get_media_library_stats",
            description="Retrieve high-level statistics: total videos, total duration, transcripts, and scenes.",
            parameters_schema={"type": "object", "properties": {}},
            handler=video_tools.get_media_library_stats,
            is_read_only=True,
            tags=["stats", "library"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="get_media_availability",
            description="Check physical media file presence, playback readiness, and relink status across roots.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string", "description": "Asset or video UUID to check"},
                },
                "required": ["asset_id"],
            },
            handler=video_tools.get_media_availability,
            is_read_only=True,
            tags=["storage", "availability"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="find_duplicate_media",
            description="Discover identical media files stored at different paths based on SHA-256 byte hashes.",
            parameters_schema={"type": "object", "properties": {}},
            handler=video_tools.find_duplicate_media,
            is_read_only=True,
            tags=["deduplication", "storage"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="get_evidence_citations",
            description="Retrieve timestamped factual citations and evidence excerpts even when original video media is offline.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Question or assertion query"},
                    "video_id": {"type": "string", "description": "Optional video UUID filter"},
                    "top_k": {"type": "integer", "description": "Number of citations to retrieve", "default": 5},
                },
                "required": ["query"],
            },
            handler=video_tools.get_evidence_citations,
            is_read_only=True,
            tags=["citations", "evidence"],
        )
    )

    engine.register_tool(
        ToolDefinition(
            name="get_capability_status",
            description="Inspect system execution profile, AI capability state, and offline status.",
            parameters_schema={"type": "object", "properties": {}},
            handler=video_tools.get_capability_status,
            is_read_only=True,
            tags=["system", "capabilities"],
        )
    )

    # Mutating tool (gated, not in default schemas)
    engine.register_tool(
        ToolDefinition(
            name="export_video_clip",
            description="Losslessly export a subclip [start_time, end_time] using FFmpeg stream copy.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "Video UUID"},
                    "start_time": {"type": "number", "description": "Start timestamp in seconds"},
                    "end_time": {"type": "number", "description": "End timestamp in seconds"},
                },
                "required": ["video_id", "start_time", "end_time"],
            },
            handler=video_tools.export_video_clip,
            is_read_only=False,
            tags=["export", "ffmpeg"],
        )
    )


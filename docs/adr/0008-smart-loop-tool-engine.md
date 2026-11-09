# ADR-0008: Shared Tool Execution Engine and Multi-Turn Smart Loop

**Status:** Accepted  
**Date:** 2026-11-09  
**Author:** Principal Software Architect & Antigravity Autonomous Loop  
**Scope:** Tool Registry, Sandboxed Dispatch, Multi-Turn Loop, and Agent Boundaries (Roadmap Step 7)

---

## 1. Context and Problem Statement

Arova Creator Intelligence exposes 12 canonical media intelligence tools over FastMCP STDIO to external desktop clients (Claude Desktop, Cursor, Antigravity, Copilot).
However:
1. Tool definitions and schemas were previously hardcoded in `mcp_server/tools/video_tools.py`, decoupled from the backend REST API.
2. Complex queries required clients to manually chain multiple individual tool calls across network boundaries.
3. There was no internal autonomous reasoning loop ("Smart Loop") capable of goal-directed tool execution (e.g. searching dialogue, retrieving citations, inspecting metadata, and synthesizing a verified answer with timestamps).
4. The system lacked a deterministic offline fallback for multi-step reasoning when running without external LLMs.

---

## 2. Decision and Architecture

We introduce:
1. **Shared Tool Execution Engine (`backend/app/services/tool_engine.py`):**
   - Canonical `ToolDefinition` registry mapping tool names, descriptions, input schemas, and callables.
   - Schema exporters for major LLM tool calling formats: OpenAI (`{"type": "function", ...}`), Google Gemini (`{"name": ..., "parameters": ...}`), Anthropic (`{"name": ..., "input_schema": ...}`), and raw JSON Schema.
   - Strict execution boundary: Read-only tools are executed safely by default; mutating tools (`export_video_clip`) are rejected with `403 Forbidden` unless `allow_mutating=True` is explicitly passed.
   - Single source of truth shared across FastMCP, REST API, CLI, and Smart Loop.

2. **Smart Loop (`backend/app/ai/smart_loop.py`):**
   - Goal-directed multi-turn agentic loop:
     - **Offline Local Mode (Deterministic Planner):** If no remote AI consent is granted or provider is `local`, executes Turn 1 (`search_video_content`) -> Turn 2 (`get_evidence_citations`) -> Turn 3 (grounded answer synthesis citing `[mm:ss - mm:ss]` intervals). Operates 100% offline with zero network egress.
     - **Remote Multi-Turn Mode:** Prompts target LLM via `AIProviderGateway` with tool schemas, dynamically parses `tool_call` actions, executes read-only tools through the engine, feeds results back into loop context, and terminates on `final_answer` or `max_turns` budget (default 5).
     - **Provenance & Telemetry:** Every Smart Loop invocation records an `AIRun` audit record with SHA-256 prompt hash, model name, provider, execution location, and tool call traces.

3. **REST API (`/api/v1/tools`, `/api/v1/agent/smart-loop`):**
   - `GET /api/v1/tools`: Discovery of canonical tools and schemas formatted for OpenAI, Gemini, or Anthropic.
   - `POST /api/v1/tools/execute`: Direct sandboxed tool execution.
   - `POST /api/v1/agent/smart-loop`: Multi-turn agent reasoning over local video media.

---

## 3. Consequences & Verification

- **Elimination of Duplication:** FastMCP and backend API share the same tool registry and schemas.
- **Strict Read-Only Enforcement:** Smart Loop execution enforces `allow_mutating=False`, ensuring agentic tool reasoning never mutates original files or state.
- **Deterministic Reliability:** In offline environments, Smart Loop provides reliable 3-turn search and citation extraction without external model dependencies.
- **Verification:** Verified via 7 unit tests in `backend/tests/unit/test_smart_loop.py` (tool listing, schema generation, dispatch, local planner, remote loop mock, REST routes). Consolidated test suite: 232/232 passed in 52.92s.

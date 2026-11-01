# Arova Creator Intelligence — Backlog & Work Breakdown Structure

**Document Authority:** Open Source Spec v1.1 & Stress Backlog v2.0  
**Status:** Managed Operational State  
**Priority Tiers:**
- **P0:** Critical Security, Data Integrity, or Release Blocker
- **P1:** Launch-Critical Approved Launch 01 Scope
- **P2:** Non-blocking Post-Launch Improvement (Blocked until Launch 01 release)
- **P3:** Gated Research Tracks (Deferred after Release 3)

---

## Workstreams Breakdown

- **`WS-ENG` (Core Engine & Pipelines):** Ingestion, probing, transcription, scene cuts, embeddings, search, Q&A.
- **`WS-MCP` (Model Context Protocol):** STDIO transport, 8 read-only tools, client configuration specs.
- **`WS-CLI` (Developer Interfaces & SDK):** `arova doctor`, `arova demo`, thin Python client wrapper.
- **`WS-SEC` (Security, Boundary & Privacy):** Local loopback default, traversal protection, source immutability, licenses.
- **`WS-QA` (Quality Assurance & Benchmarks):** Regression test suites, ML evaluation harness, health audits.
- **`WS-DOC` (Obsidian Main Brain & Governance):** `docs/` vault synchronization, ADRs, user guides.

---

## 1. P0 Backlog Items (Release Blockers & Immediate Actions)

| Task ID | Workstream | Description | Status | Dependencies | Deliverables |
|---|---|---|---|---|---|
| **TASK-001** | `WS-SEC` | Path Traversal & Source Media Immutability Verification | `DONE` | `backend/app/core/config.py` | Automated tests verifying `ALLOWED_MEDIA_ROOTS` and zero modification of source media. |
| **TASK-002** | `WS-MCP` | FastMCP STDIO Protocol & 8 Read-Only Tools Certification | `DONE` | `mcp_server/server.py` | STDIO transport with verified tool schemas and error handling. |
| **TASK-003** | `WS-ENG` | Two-Stage Hybrid Video RAG Engine (Dense + Lexical + Cross-Encoder) | `DONE` | ChromaDB + SQLite FTS5 | Reciprocal Rank Fusion ($k=60$) and PyTorch Cross-Encoder re-ranker. |
| **TASK-004** | `WS-SEC` | Resolve Source Conflicts in `.arova-loop/SOURCE_CONFLICTS.md` | `DONE` | Spec v1.1 | Official register reconciling Night Shift, CLI/SDK boundary, and FFmpeg licensing. |
| **TASK-005** | `WS-QA` | System Baseline & Security Control Gap Audit Reports | `DONE` | Test harness | `reports/audit/BASELINE.md`, `reports/security/CONTROL_GAP_ASSESSMENT.md`. |

---

## 2. P1 Backlog Items (Launch 01 Immediate Deliverables)

| Task ID | Workstream | Description | Priority | Dependencies | Acceptance Criteria |
|---|---|---|---|---|---|
| **TASK-006** | `WS-CLI` | Implement `arova doctor` Diagnostic CLI Command | `P1` | `ffprobe`, Python runtime | Inspects Python version, FFmpeg presence, SQLite FTS5, disk space, and MCP readiness. |
| **TASK-007** | `WS-CLI` | Implement `arova demo` Synthetic First-Use Workflow | `P1` | `scripts/seed_demo_media.py` | Runs complete probe, transcribe, index, and search flow on synthetic media in < 15s. |
| **TASK-008** | `WS-CLI` | Package Thin Python Client Wrapper (`arova-client`) | `P1` | FastAPI REST endpoints | Clean, typed Python wrapper exposing `health()`, `search()`, `videos()`, `ask()`. |
| **TASK-009** | `WS-DOC` | Finalize Client Setup Walkthroughs (`docs/INTEGRATIONS.md`) | `P1` | MCP Server | Step-by-step guides for Claude Desktop, Cursor, and Gemini Antigravity. |
| **TASK-010** | `WS-QA` | Automated End-to-End Release Gate Script (`scripts/release_gate.py`) | `P1` | Pytest + Vitest | Single-command release verification validating all tests and licenses before tagging. |

---

## 3. P2 Backlog Items (Post-Launch 01 Improvements — Held until v0.1 ships)

| Task ID | Workstream | Description | Priority | Status |
|---|---|---|---|---|
| **TASK-011** | `WS-ENG` | Advanced Subtitle SRT/VTT Ingestion | `P2` | `HELD` (Wait for v0.1 release) |
| **TASK-012** | `WS-ENG` | Multi-collection Drag & Drop in Frontend | `P2` | `HELD` (Wait for v0.1 release) |
| **TASK-013** | `WS-CLI` | Rich Interactive Terminal UI for CLI | `P2` | `HELD` (Wait for v0.1 release) |
| **TASK-014** | `WS-MCP` | Claude Desktop `.mcpb` Extension Package | `P2` | `HELD` (Wait for v0.1 release) |

---

## 4. P3 Backlog Items (Gated Research Tracks — Post-Release 3)

| Task ID | Workstream | Description | Priority | Status |
|---|---|---|---|---|
| **TASK-015** | `WS-ENG` | Night Shift Autonomous Background Directory Watcher | `P3` | `GATED_RESEARCH` (Post-Release 3) |
| **TASK-016** | `WS-ENG` | Multilingual Cross-Language Semantic Projection | `P3` | `GATED_RESEARCH` (Post-Release 3) |
| **TASK-017** | `WS-ENG` | Local Vision-Language Model (VLM) Frame Reasoning | `P3` | `GATED_RESEARCH` (Post-Release 3) |

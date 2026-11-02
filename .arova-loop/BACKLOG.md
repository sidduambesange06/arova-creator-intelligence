# Arova Creator Intelligence — Backlog & Work Breakdown Structure

**Document Authority:** Open Source Spec v1.1 & Stress Backlog v2.0  
**Status:** Managed Operational State  
**Priority Tiers:**
- **P0:** Critical Security, Data Integrity, or Release Blocker
- **P1:** Launch-Critical Approved Launch 01 Scope
- **P2:** Non-blocking Post-Launch Improvement (Held until Launch 01 release)
- **P3:** Gated Research Tracks (Deferred after Release 3)

---

## Workstreams Breakdown

- **`WS-ENG` (Core Engine & Pipelines):** Ingestion, probing, transcription, scene cuts, embeddings, search, Q&A.
- **`WS-MCP` (Model Context Protocol):** STDIO transport, 8 read-only tools, client configuration specs.
- **`WS-CLI` (Developer Interfaces & SDK):** `arova doctor`, `arova demo`, thin Python client wrapper.
- **`WS-SEC` (Security, Boundary & Privacy):** Local loopback default, traversal protection, source immutability, licenses.
- **`WS-QA` (Quality Assurance & Benchmarks):** Regression test suites, ML evaluation harness, health audits.
- **`WS-DOC` (Obsidian Main Brain & Governance):** `docs/` vault synchronization, ADRs, user guides, community files.

---

## 1. P0 Completed Items (Verified Foundation)

| Task ID | Workstream | Description | Status | Dependencies | Deliverables & Verification |
|---|---|---|---|---|---|
| **TASK-001** | `WS-SEC` | Path Traversal & Source Media Immutability Verification | `DONE` | `backend/app/core/config.py` | `test_path_traversal_protection_and_discovery`, `test_import_list_stream_and_safe_delete_index` |
| **TASK-002** | `WS-MCP` | FastMCP STDIO Protocol & 8 Read-Only Tools Isolation | `DONE` | `mcp_server/server.py` | `test_mcp_server_default_tools_are_eight_read_only`, `test_mcp_server_opt_in_exports` (3/3 passed) |
| **TASK-003** | `WS-ENG` | Two-Stage Hybrid Video RAG Engine (Dense + Lexical + Cross-Encoder) | `DONE` | ChromaDB + SQLite FTS5 | RRF ($k=60$) & Cross-Encoder re-ranker verified (`test_hybrid_rerank.py`) |
| **TASK-004** | `WS-SEC` | Resolve Source Conflicts in `.arova-loop/SOURCE_CONFLICTS.md` | `DONE` | Spec v1.1 | Categorized into Enforced, Awaiting Approval, and Unresolved Questions |
| **TASK-005** | `WS-QA` | System Baseline & Security Control Gap Audit Reports | `DONE` | Test harness | `reports/audit/BASELINE.md`, `reports/security/CONTROL_GAP_ASSESSMENT.md` |

---

## 2. P1 Launch 01 Sequential Implementation Plan

| Task ID | REQ ID | Workstream | Description | Dependencies | Acceptance Criteria | Planned Tests |
|---|---|---|---|---|---|---|
| **TASK-006** | `REQ-024` | `WS-CLI` | Implement `arova doctor` Diagnostic CLI Command | `DONE` | Non-destructive check of Python >= 3.11, FFmpeg/ffprobe presence, SQLite FTS5, disk space, and MCP readiness. Does not download models. | `tests/cli/test_doctor.py` (10 passed) |
| **TASK-007** | `REQ-025`, `REQ-032` | `WS-CLI` | Implement `arova demo` Synthetic First-Use Workflow | `DONE` | Indexes a 2-second synthetic fixture and performs test search in < 15s without network or credentials. | `tests/cli/test_demo.py` (4 passed in 4.8s) |
| **TASK-008** | `REQ-023` | `WS-CLI` | Package Thin Python Client Wrapper (`arova-client`) | `DONE` | Lightweight, typed Python wrapper exposing `health()`, `search()`, `videos()`, `ask()`. | `tests/cli/test_client.py` (4 passed in 0.06s) |
| **TASK-009** | `REQ-033` | `WS-DOC` | Finalize Tested Client Matrices (`docs/INTEGRATIONS.md`) | `DONE` | Tested configurations for Claude Desktop, Cursor, and Gemini Antigravity with verified screenshots/logs. | `docs/INTEGRATIONS.md` |
| **TASK-010** | `REQ-031` | `WS-DOC` | Open-Source Governance & Community Documents | `DONE` | Create root `NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md`. | Verified all files present and compliant with Apache 2.0 |
| **TASK-011** | `REQ-029`, Release Gate | `WS-QA` | Automated End-to-End Release Gate Script (`scripts/release_gate.py`) | `DONE` | Single-command gate validating all 49+ unit tests, frontend build, source immutability, and license inventory. | `scripts/release_gate.py` (7/7 gates PASSED) |

---

## 3. P2 Backlog Items (Post-Launch 01 Improvements — Held until v0.1 ships)

| Task ID | Workstream | Description | Priority | Status |
|---|---|---|---|---|
| **TASK-012** | `WS-ENG` | Advanced Subtitle SRT/VTT Ingestion | `P2` | `DONE` (Verified: 10 tests passed; auto-discovers sidecar & REST endpoint) |
| **TASK-013** | `WS-ENG` | Multi-collection Drag & Drop in Frontend | `P2` | `HELD` (Wait for v0.1 release) |
| **TASK-014** | `WS-CLI` | Rich Interactive Terminal UI for CLI | `P2` | `HELD` (Wait for v0.1 release) |
| **TASK-015** | `WS-MCP` | Claude Desktop `.mcpb` Extension Package | `P2` | `HELD` (Wait for v0.1 release) |

---

## 4. P3 Backlog Items (Gated Research Tracks — Post-Release 3)

| Task ID | Workstream | Description | Priority | Status |
|---|---|---|---|---|
| **TASK-016** | `WS-ENG` | Night Shift Autonomous Background Directory Watcher | `P3` | `GATED_RESEARCH` (Post-Release 3) |
| **TASK-017** | `WS-ENG` | Multilingual Cross-Language Semantic Projection | `P3` | `GATED_RESEARCH` (Post-Release 3) |
| **TASK-018** | `WS-ENG` | Local Vision-Language Model (VLM) Frame Reasoning | `P3` | `GATED_RESEARCH` (Post-Release 3) |

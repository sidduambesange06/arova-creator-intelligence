# M1 — API, SDK, MCP Parity & Contract Freeze Report (`V12 Phase 0` Completion)

**Project:** Arova Creator Intelligence (`v0.1.0-alpha.2`)  
**Milestone:** `M1` — API, SDK, MCP Parity & Contract Freeze (completes `V12 Phase 0: Foundation & Contract Freeze`; `V12 Phase 1: Indic Creator Bench` begins at `M2`)  
**Authoritative Loop:** `V11.0` Autonomous Engineering Runtime · `V12` Product Roadmap (`M0–M16` across `V12 Phase 0–5+`)  
**Git Baseline (`HEAD`):** `fce662f1460d262664530f36dde260e7e0a8b815` on `test/tears-of-steel-full-media-validation` (`15` commits ahead of `origin/main` `96f85e6`, `10` commits ahead of `origin/feat/task4-media-discovery` `8c7663f`)  
**Date:** `2026-11-15`  
**Status:** `VERIFIED PASS — READY FOR FOUNDER APPROVAL (NO COMMITS MADE)`

---

## 1. Executive Summary

`M1` resolves `ISS-019` and freezes the developer-facing search, Q&A, summary consent, Python SDK, FastMCP server, and shared tool-engine contracts across Arova Creator Intelligence without adding new runtime dependencies or touching `M2–M16` scope.

### Key Deliverables Completed
1. **5-Gate Consent Evaluation & Authentic `consent_source` Reporting (`ISS-019` Part 1):** Fixed `/api/v1/ai/summarize` and `/api/v1/ai/ask` to resolve real `Library.execution_profile`, `LibraryRoot.policy`, multi-level `scope_id` hierarchies, provider registration + `supported_capabilities`, expiry/budget limits, and loopback local execution without synthetic `Default Root`/`Default Library` interference or broken string heuristics.
2. **Python SDK Filter & Bypass Rejection Parity (`ISS-019` Part 2):** Added `video_id` and `channel="all"` parameters to `ArovaClient.search()` and `channel="all"`, `provider`, and `consent_remote_ai` parameters to `ArovaClient.ask()`, with strict client-side `ValueError` validation via `_validate_channel()`.
3. **MCP & Shared Tool Engine Contract Parity (`ISS-019` Part 3):** Added `video_id` and `channel` (`Literal["all", "speech", "visual", "multimodal"] = "all"`) to MCP `search_video_content`, added `channel` to `get_evidence_citations`, synchronized `ToolExecutionEngine` schemas, and updated `mcp_server/server.py` docstring from stale `"8 official"` to `"12 official"` while preserving the `12` read-only default + `1` opt-in `export_video_clip` (`AROVA_ENABLE_MCP_EXPORTS` / `--enable-exports`) boundary.
4. **Authoritative Channel Contract Freeze:** Enforced `VALID_SEARCH_CHANNELS = ("all", "speech", "visual", "multimodal")` cleanly via `validate_search_channel()` across retrieval (`hybrid_search.py`), REST/OpenAPI (`search.py`), service (`summary_service.py`), SDK (`arova/client.py`), MCP (`mcp_server/tools/video_tools.py`, `mcp_server/server.py`), and `ToolExecutionEngine` (`tool_engine.py`), eliminating silent fallback to `"all"` and removing stale `spoken | visual_ocr | summary` doc drift.
5. **Documentation, CI Reconciliation & Audit Alignment:** Updated `docs/MCP_TOOLS.md`, `docs/mcp-guide.md`, `docs/INTEGRATIONS.md`, `README.md`, Obsidian vault docs (`docs/`), `reports/product-acceptance/CURRENT_DEVELOPMENT_STATE_AUDIT.{md,json}`, and `.arova-loop/*`, and reconciled PR #11 (`8c7663f`) CI failure history against fix commit `742a4a2`.

### M1 Acceptance Gates (`G1`–`G8`)

| Gate | Requirement | Status | Primary Evidence |
|---|---|---|---|
| **`G1`** | Baseline Reproducibility & Audit Reconciliation | **`PASS`** | Reconciled at `HEAD = fce662f` + PR #11 (`8c7663f`) fix `742a4a2` |
| **`G2`** | Consent-Source & 5-Gate Enforcement (`/ai/summarize`, `/ai/ask`) | **`PASS`** | `gateway.py`, `summary_service.py`, `search.py`, `test_byo_ai_gateway.py` |
| **`G3`** | Python SDK (`ArovaClient`) Filter & Fail-Closed Parity | **`PASS`** | `arova/client.py` (`search`, `ask`), `test_client.py` |
| **`G4`** | FastMCP & Shared `ToolExecutionEngine` Parity (`12` read-only + `1` gated) | **`PASS`** | `mcp_server/server.py`, `video_tools.py`, `tool_engine.py`, `test_mcp_tools.py`, `test_smart_loop.py` |
| **`G5`** | Frozen Channel Contract (`all \| speech \| visual \| multimodal`) & OpenAPI Enum | **`PASS`** | `hybrid_search.py`, `search.py`, `test_hybrid_rerank.py` |
| **`G6`** | Documentation, Obsidian Vault & `.arova-loop/` Synchronization | **`PASS`** | `docs/`, `README.md`, `CURRENT_DEVELOPMENT_STATE_AUDIT.{md,json}`, `.arova-loop/*` |
| **`G7`** | Full Backend/MCP/Frontend Test Suite & `7/7` System Health Audit | **`PASS`** | `scripts/system_health_audit.py` + `reports/LATEST_HEALTH_REPORT.md` |
| **`G8`** | Git Safety, Security, Zero New Deps & Apache 2.0 IP Boundary | **`PASS`** | Zero commits/pushes (`HEAD = fce662f`), zero new deps, Strict IP scan clean |

---

## 2. Upstream GitHub Research Audit (`2026-11-14`)

Eleven upstream repositories (6 core M1/V12 references + 5 future M2+ ecosystem references) were inspected via live GitHub metadata on `2026-11-14` strictly for architectural reference and license screening; zero external dependencies were added in `M1`.

### 2.1 Core Repositories (6)

| Repository | Default Branch | Head SHA | Last Commit (UTC) | License | Stars | M1/V12 Alignment & Governance Note |
|---|---|---|---|---|---:|---|
| `vaibhav-space/vindex` | `main` | `b500081c20` | `2026-11-08T09:22:21Z` | `MIT` | 20 | Reference local video indexing patterns; ACI retains its own SQLite/FTS5 + vector pipeline. |
| `m-bain/whisperX` | `main` | `b904f02b7e` | `2026-11-12T17:34:05Z` | `BSD-2-Clause` | 25,251 | Word-level alignment reference for `M2` ASR provenance; deferred out of `M1`. |
| `AI4Bharat/IndicConformerASR` | `master` | `3a4c52d0e9` | `2025-06-20T10:29:10Z` | `MIT` | 107 | Indic ASR reference for `M2+` evaluation against ACI FLEURS baseline; deferred out of `M1`. |
| `PrefectHQ/fastmcp` | `main` | `a8745d61e6` | `2026-11-14T01:40:33Z` | `Apache-2.0` | 28,415 | Validates FastMCP typed `Literal[...]` schema emission used directly in `mcp_server/server.py`. |
| `schemathesis/schemathesis` | `master` | `7bb356c55b` | `2026-11-13T12:31:21Z` | `MIT` | 3,776 | OpenAPI contract testing pattern; NOT installed in `.venv` — not added per M1 zero-new-deps rule. |
| `openapi-generators/openapi-python-client` | `main` | `46a4340cf4` | `2026-11-07T21:17:38Z` | `MIT` | 2,002 | Reference typed SDK generation conventions; ACI preserves thin zero-bloat `ArovaClient` (5 methods). |

### 2.2 Future M2+ Ecosystem Repositories (5)

| Repository | Default Branch | Head SHA | Last Commit Date | License | Stars | Governance / Isolation Assessment |
|---|---|---|---|---|---:|---|
| `cspenn/supoclip` | `main` | `bd332926af` | `2026-06-29` | **`AGPL-3.0`** | 0 | **STRICT ISOLATION WARNING:** Strong copyleft (`AGPL-3.0`) is incompatible with ACI's `Apache-2.0` license. **Never copy or adapt code from `supoclip`.** |
| `artbyjazi/autoclip` | `main` | `5d0eac36fa` | `2026-08-01` | `MIT` | 288 | Permissive reference only for future clip-scoring workflows (`M2+`). |
| `pyannote/pyannote-audio` | `main` | `0d6f291328` | `2026-11-09` | `MIT` | 10,794 | Future speaker diarization reference (`M2+`). |
| `lancedb/lancedb` | `main` | `d67ec47921` | `2026-11-14` | `Apache-2.0` | 11,896 | Future multimodal vector store scaling reference (`M2+`). |
| `AcademySoftwareFoundation/OpenTimelineIO` | `main` | `bad7ab5a40` | `2026-11-10` | `Apache-2.0` | 2,080 | Future NLE timeline interoperability reference (`M2+`). |

---

## 3. Frozen Contract Matrix (REST, SDK, MCP, ToolEngine)

### 3.1 Authoritative Retrieval Channel Contract

- **Frozen Enum:** `VALID_SEARCH_CHANNELS = ("all", "speech", "visual", "multimodal")` (defined in `backend/app/ai/retrieval/hybrid_search.py` and mirrored in `arova/client.py`, `backend/app/services/tool_engine.py`, and `mcp_server/server.py`).
- **Fail-Closed Validation:** Invalid values are rejected loudly across every entrypoint (`ValueError` in SDK, retrieval, service, and MCP tools; HTTP `400` in `ask_video_ai` when catching `ValueError`, HTTP `422` via Pydantic schema validation on `SemanticSearchRequest` / `AskQuestionRequest`, and JSON schema enum rejection in `FastMCP` / `ToolExecutionEngine`).

### 3.2 Cross-Surface Parity Table

| Capability | REST API (`search.py`) | Python SDK (`arova/client.py`) | FastMCP (`mcp_server/`) | Shared Engine (`tool_engine.py`) |
|---|---|---|---|---|
| **Hybrid Search** | `POST /api/v1/search/semantic` (`SemanticSearchRequest`: `query`, `top_k=10`, `use_reranker=True`, `video_id`, `channel`) | `ArovaClient.search(query, top_k=5, use_reranker=True, video_id=None, channel="all")` | `search_video_content(query, top_k=5, use_reranker=True, video_id=None, channel="all")` | `search_video_content` schema includes `video_id` & `channel` (`enum`, default `"all"`) |
| **Evidence Citations** | `/api/v1/search/semantic` & transcript search endpoints | Covered via `search()` / `ask()` | `get_evidence_citations(query, video_id=None, top_k=5, channel="all")` | `get_evidence_citations` schema includes `channel` (`enum`, default `"all"`) |
| **Grounded Q&A** | `POST /api/v1/ai/ask` (`AskQuestionRequest`: `query`, `video_id`, `channel`, `api_key`, `consent_remote_ai`, `provider`, `model`, `base_url`) | `ArovaClient.ask(question, video_id=None, channel="all", provider=None, consent_remote_ai=False)` | Grounded retrieval + `summarize_video` | Grounded tool loop via `ToolExecutionEngine` (`12` read-only tools) |
| **Summary & Provenance** | `POST /api/v1/ai/summarize` (`SummarizeRequest` -> `SummarizeResponse` with real `consent_source`, `remote_egress`, `provider`, `egress_data_categories`) | — | `summarize_video(video_id)` (read-only transcript synthesis) | `summarize_video` tool dispatch |
| **MCP Export Boundary** | N/A | N/A (5 read-only methods: `health`, `list_videos`, `get_video`, `search`, `ask`) | **12 default read-only tools**; 13th `export_video_clip` gated on `AROVA_ENABLE_MCP_EXPORTS` (`1`/`true`/`yes`) or `--enable-exports` | Read-only default tool dispatch (`12` registered tools) |

**The 12 Default Read-Only FastMCP Tools:**
`list_videos`, `get_video_metadata`, `search_video_content`, `search_transcripts`, `find_video_clips`, `summarize_video`, `get_video_chapters`, `get_media_library_stats`, `get_media_availability`, `find_duplicate_media`, `get_evidence_citations`, `get_capability_status`.  
**Gated 13th Tool (Opt-In Only):** `export_video_clip`.

---

## 4. 5-Gate Consent Evaluation & `consent_source` Reporting (`ISS-019`)

Before `M1`, `backend/app/api/routes/search.py` inferred `SummarizeResponse.consent_source` via string heuristics without inspecting persisted `AIConsent` records or full video/library policy scopes evaluated in `summary_service.py`, while `gateway.py` lacked capability checks, multi-scope ID resolution, and loopback metadata clearing.

### Architectural Fix Implemented
1. **`backend/app/ai/providers/gateway.py`:**
   - Updated `evaluate_consent` to validate provider registration and `supported_capabilities`, match multi-scope IDs (`str`, `set`, `list`, `tuple`, wildcard `"*"` / `"global"`, and `scope_type == "global"`), enforce `expires_at` (`<= now`) and `budget_limit` (`<= 0`), and check optional `data_categories`.
   - Updated `generate_llm_response` and `generate_structured_json` to accept/propagate `scope_id` and clear `consent_source = None` and `consent_id = None` whenever `not response.remote_egress` (ensuring local loopback execution never reports remote consent attribution).
2. **`backend/app/services/summary_service.py`:**
   - Added `_resolve_video_policy_context()` resolving `Library.execution_profile`, `LibraryRoot.policy`, and `video_id`/`asset_id`/`version_id`/`root_id`/`library_id` scope IDs while ignoring synthetic `Default Root` + `Default Library` backfill entries created by schema migrations.
   - Added `_attach_summary_provenance()` and enforced 5-gate evaluation across both `generate_video_summary()` and `answer_video_question()`, properly separating DB cache hits from remote upgrade attempts without falsely attributing remote egress on unconsented cached responses.
3. **`backend/app/api/routes/search.py`:**
   - Updated `summarize_video` to populate response metadata strictly from real gateway/service provenance (`_remote_egress`, `_provider`, `_consent_source`, `_egress_data_categories`).

### Scenario Coverage (Verified in `backend/tests/unit/test_byo_ai_gateway.py`)
`test_m1_summarize_and_ask_consent_source_all_scenarios` and `test_m1_provider_missing_capability_and_loopback_consent_source` verify:
- Remote consent resolution across `video_id`, `asset_id`, `version_id`, `root_id`, `library_id`, and global scopes.
- Per-request `consent_remote_ai` grant attribution vs persisted `AIConsent` grants.
- Local fallback with cleared `consent_source` / `consent_id` when consent is missing, expired, budget-exhausted (`budget_limit <= 0`), category-disallowed, or blocked by `Library` / `LibraryRoot` policy.
- Missing provider `supported_capabilities` rejection.
- Cached summary responses vs remote upgrade eligibility.
- Non-interference from synthetic `Default Root` and `Default Library` migration backfill rows.

---

## 5. Git & PR #11 (`8c7663f`) CI Reconciliation

- **Active Local Branch:** `test/tears-of-steel-full-media-validation` at `HEAD = fce662f1460d262664530f36dde260e7e0a8b815`.
- **PR #11 Commit Checked:** `8c7663fe446567b4a3eb41cf0096ac1170346a5e` (`origin/feat/task4-media-discovery`):
  - `Backend Pytest & MCP Suite`: `success`
  - `Frontend Vitest & TypeScript Build`: `success`
  - `System Health & Security Audit` (run `41800907154` / job `126476512694`): `failure` — root cause was `scripts/system_health_audit.py:347` asserting `8` read-only MCP tools after `mcp_server/server.py` already registered `12` read-only tools (plus a 120s pytest timeout). That failure was fixed on the local branch in commit `742a4a2` prior to `fce662f`.
- **Founder Merge Recommendation (Post-M1 Commit Approval):**
  1. Founder reviews M1 working-tree changes (`git status` / `git diff`).
  2. Founder authorizes atomic M1 commit(s) and pushes/merges into target branch (`feat/task4-media-discovery` / `main`) so CI picks up `742a4a2` + `M1`.
  3. Zero git mutations (`commit`, `push`, `reset`, `clean`, `checkout`) were performed by the agent.

---

## 6. Verification & System Health

Post-remediation verification observed on final M1 closure edits:
- `.\.venv\Scripts\python.exe -m pytest backend/tests mcp_server/tests -q`: **242 passed in 41.76s** (`+9` M1 regression tests over M0's `233`: `+6` initial M1 + `+3` closure remediation tests).
- `npm --prefix frontend test -- --run`: **7 test files, 18 tests passed in 8.73s**.
- `npm --prefix frontend run build`: **`0` TypeScript errors, 45 modules built in 1.86s**.
- `.\.venv\Scripts\python.exe scripts\system_health_audit.py`: **`HEALTHY` (`7/7` checks passed in `58.04s` at `2026-11-14T18:54:24Z`, re-verified after final doc updates in `reports/LATEST_HEALTH_REPORT.md` & `reports/health_report_latest.json`)**.

---

## 7. Security, Privacy & Governance Review

- **Local-First & Fail-Closed Egress:** Unconsented or policy-blocked AI requests never reach remote providers; loopback executions clear `consent_source` and `consent_id`.
- **Source Media Immutability & Path Traversal:** No changes weakened `ALLOWED_MEDIA_ROOTS`, path normalization, or read-only source video protections.
- **Read-Only Default MCP Contract:** Default FastMCP registration remains strictly 12 read-only tools; `export_video_clip` stays disabled unless explicitly opted in via `AROVA_ENABLE_MCP_EXPORTS` or `--enable-exports`.
- **Apache 2.0 IP Boundary:** Zero proprietary commercial feature names or code paths introduced; `cspenn/supoclip` (`AGPL-3.0`) strictly excluded.
- **Code Hygiene & Ponytail Review:** Zero `TODO`/`FIXME`/`XXX`/`HACK` markers introduced; zero new runtime dependencies installed (`schemathesis` skipped); dead duplicate block in `summary_service.py` removed.

---

## 8. Next Milestone Recommendation

Proceed after Founder approval to **`M2` (`V12 Phase 1: Indic Creator Bench` — Benchmark Dataset Schema, Manifest Loader, 10-Clip Smoke Corpus & Batch/ASR Provenance Prep)**, keeping `M1` API/SDK/MCP channel (`all | speech | visual | multimodal`) and 5-gate `consent_source` contracts frozen as the `V12 Phase 0` foundation. See [M1_FINAL_CLOSURE_AUDIT.md](file:///c:/Users/Siddhu%20Ambesanage/Downloads/OPEN%20SORCE%20DEVELOPMENT/reports/product-acceptance/M1_FINAL_CLOSURE_AUDIT.md) for the independent `G1`–`G8` closure verification package.

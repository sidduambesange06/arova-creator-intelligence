# Arova Creator Intelligence — Architectural Decision Log (ADR)

**Document Authority:** Open Source Spec v1.1  
**Status:** Managed Operational State  

---

## Architecture Decision Records

### ADR-001: Reciprocal Rank Fusion ($k=60$) for Two-Stage Hybrid Retrieval
- **Date:** 2026-10-31
- **Status:** Accepted & Implemented
- **Context:** Dense vector search excels at high-level semantic intent but struggles with exact acronyms, proper nouns, and technical jargon. Lexical BM25 (SQLite FTS5) excels at keyword precision but misses synonyms.
- **Decision:** Combine top-$k$ outputs of dense ChromaDB and lexical SQLite FTS5 using Reciprocal Rank Fusion:
  $$\text{RRF}(d) = \sum_{m \in \{\text{dense}, \text{lexical}\}} \frac{1}{60 + r_m(d)}$$
- **Consequences:** Provides robust, query-type resilient retrieval across both technical terminology and conceptual queries without tuning heuristic alpha blending parameters.

### ADR-002: Local FastMCP Server STDIO Transport
- **Date:** 2026-10-31
- **Status:** Accepted & Implemented
- **Context:** AI agents (Claude Desktop, Cursor, Copilot, Antigravity) need access to local video libraries without exposing unauthenticated network ports on the host.
- **Decision:** Implement Model Context Protocol using FastMCP over local STDIO. Expose 8 read-only tools. Reserve standard output exclusively for JSON-RPC messages; direct logs to stderr.
- **Consequences:** Eliminates network attack surface, prevents unauthorized LAN access, and simplifies agent configuration.

### ADR-003: Visual-Text Dual Memory Fusion
- **Date:** 2026-10-31
- **Status:** Accepted & Implemented
- **Context:** Video content contains critical information displayed on slides, code editors, and diagrams that is not spoken aloud.
- **Decision:** Extract on-screen text from keyframe thumbnails and fuse it into the corresponding timestamped sliding-window chunks with explicit `[On-Screen Visual Text]: ...` markers.
- **Consequences:** Enables unified dense vector and lexical FTS5 retrieval over both spoken speech and visual presentation content.

### ADR-004: Grounded Video Q&A with Timecode Citations
- **Date:** 2026-11-01
- **Status:** Accepted & Implemented
- **Context:** Creators and developers need factual answers to specific questions about video content with verifiable receipts rather than hallucinated summaries.
- **Decision:** Synthesize grounded Q&A responses strictly from retrieved transcript passages, formatting citations as clickable time intervals `[mm:ss - mm:ss]` that allow one-click video player seeking.
- **Consequences:** Eliminates hallucination risk; every claim is tied to verified video evidence.

### ADR-005: FastMCP Default Read-Only Isolation & Developer Opt-In for Exports
- **Date:** 2026-11-01
- **Status:** Accepted & Implemented (Commit `13dd684`)
- **Context:** Open Source Spec v1.1 (§3.2, §15.3) dictates that AI agents in Launch 01 must only have read-only tools. The `export_video_clip` tool writes MP4 subclips to disk.
- **Decision:** Isolate the default MCP toolset to strictly the 8 read-only retrieval tools. Gate `export_video_clip` behind an explicit developer opt-in (`AROVA_ENABLE_MCP_EXPORTS=1` or `--enable-exports`).
- **Consequences:** Strictly enforces the read-only agent contract while preserving subclip slicing capability for explicit developer opt-in.

### ADR-006: Canonical Task Numbering & Deliverable Separation for Launch 01
- **Date:** 2026-11-01
- **Status:** Accepted & Implemented
- **Context:** Early drafts assigned `TASK-010` to the automated release gate, while community governance documents (`NOTICE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` per Spec §10.2) were informal deliverables.
- **Decision:** Reconcile task IDs into a single canonical sequence:
  - `TASK-006`: `arova doctor` diagnostic CLI command (`WS-CLI`, `REQ-024`) — `VERIFIED`
  - `TASK-007`: `arova demo` synthetic first-use flow (`WS-CLI`, `REQ-025`, `REQ-032`) — `VERIFIED`
  - `TASK-008`: Thin Python client wrapper `arova-client` (`WS-CLI`, `REQ-023`) — `VERIFIED`
  - `TASK-009`: Tested client integration matrices in `docs/INTEGRATIONS.md` (`WS-DOC`, `REQ-033`) — `VERIFIED`
  - `TASK-010`: Open-source community governance files (`WS-DOC`, `REQ-031`) — `VERIFIED`
  - `TASK-011`: Automated release gate verification script (`WS-QA`, `REQ-029`) — `VERIFIED`
- **Consequences:** Provides exact 1:1 requirement traceability across all registers and eliminates ambiguity between release verification and community documentation.

### ADR-007: Staged Release Governance (Alpha vs Beta/Stable Scope Delineation)
- **Date:** 2026-11-01
- **Status:** Accepted & Enforced
- **Context:** An open-source developer Alpha (`v0.1.0-alpha`) requires verified local core engine mechanics, safe queries, bounded filesystems, prompt defanging, and robust recovery, but does not warrant enterprise SaaS certification or blocking local developer previews on external multi-machine non-developer physical setups.
- **Decision:** Separate release gates into staged milestones:
  - **Alpha (`v0.1.0-alpha`):** All 12 automated checks (Backend, Frontend, FastMCP, Doctor, Demo, 500-Video Stress, 215 Red-Team Cases, 100-Query Benchmark, Fault-Injection Resiliency, and CycloneDX SBOM) 100% passing. Localhost-only binding (`127.0.0.1`), 8 default read-only MCP tools, parameterized SQL, and source media immutability.
  - **Beta (`v0.2.0-beta`):** External non-developer multi-machine validation across independent macOS and Linux hosts; live Claude Desktop / Cursor GUI manual verification; PyPI package distribution.
  - **Stable (`v1.0.0`):** Model Context Protocol official registry publication and enterprise backward compatibility.
- **Consequences:** Unblocks open-source Alpha preview testing with zero false claims of enterprise certification, while cleanly staging broader ecosystem QA on the Beta/Stable roadmap.

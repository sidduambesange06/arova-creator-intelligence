# Arova Creator Intelligence — Source Conflicts Register

**Document Class:** Operational Governance  
**Authority Hierarchy:**
1. Open Source Specification & Launch 01 Plan (`AROVA_CREATOR_INTELLIGENCE_OPEN_SOURCE_SPEC_AND_LAUNCH_01.md` / `v1.1`)
2. Actual Repository Source Code and Tests
3. Latest Stress-Tested Backlog, Version 2.0
4. Existing `AGENTS.md` and Repository Engineering Rules
5. Development Plans and Staged Roadmaps (contextual only)
6. Obsidian Main Brain (`docs/`)
7. Assumptions (never treated as approved requirements)

---

## Conflict Matrix

| Conflict ID | Topic | Involved Sources | Exact Difference | Impact | Safe Interpretation | Proposed Resolution | Approval Required? |
|---|---|---|---|---|---|---|---|
| **CONF-001** | Night Shift Sequencing | Older Master Strategy Plan vs Stress Backlog v2.0 vs Spec v1.1 | Older plan mentions Night Shift background batch indexing early; Stress Backlog v2.0 and Spec explicitly defer Night Shift to a gated research track after Release 3. | Prevents scope explosion into complex unattended background processing before core engine stability is proven. | Night Shift is strictly excluded from Launch 01. No unattended indexing or background watchers in v0.1. | Enforce Launch 01 boundary: Night Shift is marked as P3 / Post-Release 3 research track in `BACKLOG.md`. | **Yes (Propose approval)** |
| **CONF-002** | CLI & SDK Scope Boundary | Open Source Spec v1.1 (§4.2, §4.3) vs Stress Backlog v2.0 (Batch 6) | Spec v1.1 mandates a minimal CLI diagnostic surface (`arova doctor`, `arova demo`, manual config) and thin Python client wrapper; Stress Backlog groups expanded SDK/CLI tooling into Batch 6. | Distinguishes lightweight initial developer interface from full client SDK distribution. | Launch 01 implements only the minimal CLI (`arova doctor`, `arova demo`, manual client config output) and thin Python REST client wrapper. Expanded CLI/SDK stability belongs in Batch 6. | Deliver minimal CLI & thin SDK for Launch 01; park Batch 6 expanded interfaces in Future Work backlog. | **Yes (Propose approval)** |
| **CONF-003** | FFmpeg Packaging & Licensing | Older Backlog notes vs Open Source Spec v1.1 (§8, §1.2) | Older notes proposed bundling an FFmpeg binary; Spec v1.1 and AGENTS rules require auditing exact binary build flags and GPL/LGPL obligations, preferring system FFmpeg. | Shipping a bundled FFmpeg binary without legal/codec build audit risks GPL licensing contagion. | Do not bundle an unverified binary. Require system-installed FFmpeg verified by `arova doctor`, with clear install instructions for Windows, macOS, and Linux. | Document system dependency in `docs/installation.md`, verify presence in `arova doctor`, and document deviation from bundled binary proposal. | **Yes (Propose approval)** |
| **CONF-004** | Commercial IP vs Open Source Boundary | Internal Master Strategy vs Spec v1.1 (§1.4, §16) vs `AGENTS.md` | Master Strategy describes commercial Creator OS, Molty AI, Brand Deal CRM, and Cloud Studio; Spec v1.1 strictly restricts this repository to Apache-2.0 local video intelligence engine. | Prevents proprietary commercial IP leakage and distraction from open-source local-first video RAG core. | Strict isolation: Zero commercial Creator OS / Molty AI features in this repo. No cloud hosting, no paid tiers, no studio waitlists. | Maintain strict Apache-2.0 boundary. Document exclusions in Project Charter and `AGENTS.md`. | **Yes (Propose approval)** |
| **CONF-005** | MCP Server Toolset: 8-Tool Read-Only vs 9-Tool Implementation | Spec v1.1 (§3.2, §15.3) vs `mcp_server/server.py` | Spec v1.1 specifies an 8-tool strictly read-only MCP server for AI agents. The current implementation in `mcp_server/server.py` registers 9 tools including `export_video_clip` (disk write / export). | Exposing state-mutating file export to agents violates the strict read-only MCP contract for Launch 01. | Launch 01 AI agent toolset must be strictly read-only. `export_video_clip` is a local developer utility and should either require explicit user confirmation or be gated behind a separate flag. | Keep the 8 read-only tools active by default for AI agents (`list_videos`, `get_video_metadata`, `search_video_content`, `search_transcripts`, `find_video_clips`, `summarize_video`, `get_video_chapters`, `get_media_library_stats`). Gate `export_video_clip` behind `--enable-exports` or retain as developer-only REST endpoint. | **Yes (Propose approval)** |

---

## Detailed Conflict Analysis

### CONF-001: Night Shift Background Watcher
- **Spec Authority:** Open Source Spec v1.1 explicitly excludes autonomous file management, background ingestion watchers, and unattended daemon processing from Launch 01.
- **Stress Backlog v2.0 Decision:** Explicitly gates Night Shift as an experimental research track to be tackled after Release 3.
- **Resolution:** No Night Shift code will be introduced in Launch 01. All indexing remains user-triggered, deterministic, and bounded.

### CONF-002: SDK and CLI Boundaries
- **Spec Authority:** Section 4.2 requires a thin Python client over FastAPI REST endpoints. Section 4.3 outlines `arova doctor` and `arova demo` as diagnostic / first-use commands.
- **Stress Backlog v2.0:** Batch 6 schedules rich CLI commands, interactive shell, and client SDK release packaging.
- **Resolution:** Implement minimal `arova doctor` and `arova demo` commands as part of the core package; defer complex CLI interactive menus to Batch 6.

### CONF-003: FFmpeg Binary Packaging
- **Spec Authority:** Section 8 notes that FFmpeg contains varied codec licensing (LGPL vs GPL build options).
- **Resolution:** Rather than distributing an unverified binary, `arova doctor` inspects the host's `ffmpeg` and `ffprobe` availability on PATH, returning clean remediation guidance for winget/brew/apt.

### CONF-004: IP Boundary
- **Spec Authority:** Apache-2.0 license strictly enforced. Commercial modules (Creator OS, Molty AI, Brand CRM, Browser Studio) are completely banned from this repository.
- **Resolution:** Maintained and validated by automated pre-commit / pre-invocation checks.

### CONF-005: 8-Tool Read-Only MCP Contract
- **Spec Authority:** Section 3.2: "The first release should be read-only for AI agents... Do not expose arbitrary shell commands, arbitrary filesystem reads, source deletion, model downloads or unattended exports as agent-callable tools in v0.1."
- **Current State:** `mcp_server/server.py` has 9 tools: `export_video_clip` performs disk writes to `data/clips`.
- **Resolution:** Document the 8 core read-only tools as the official agent contract. Reconcile `docs/MCP_TOOLS.md` to document the 8 core retrieval tools.

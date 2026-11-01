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

## 1. Enforced Architectural Boundaries (Zero Approval Needed)

| Conflict ID | Topic | Involved Sources | Exact Difference | Impact | Enforced Policy | Status |
|---|---|---|---|---|---|---|
| **CONF-004** | Commercial IP vs Open Source Boundary | Internal Master Strategy vs Spec v1.1 (§1.4, §16) vs `AGENTS.md` | Master Strategy describes commercial Creator OS, Molty AI, Brand Deal CRM, and Cloud Studio; Spec v1.1 strictly restricts this repository to Apache-2.0 local video intelligence engine. | Prevents proprietary commercial IP leakage and maintains focus on local video RAG core. | **Strict Isolation Enforced:** Zero commercial Creator OS / Molty AI features in this repo. No cloud hosting, no paid tiers, no studio waitlists. Governed by pre-commit hooks and `AGENTS.md`. | **ENFORCED** |

---

## 2. Proposed Resolutions (Awaiting Phase 1 Approval)

| Conflict ID | Topic | Involved Sources | Exact Difference | Impact | Safe Interpretation | Proposed Resolution | Approval Status |
|---|---|---|---|---|---|---|---|
| **CONF-001** | Night Shift Sequencing | Older Master Strategy Plan vs Stress Backlog v2.0 vs Spec v1.1 | Older plan mentions Night Shift background batch indexing early; Stress Backlog v2.0 and Spec explicitly defer Night Shift to a gated research track after Release 3. | Prevents scope explosion into complex background watchers before core engine stability is proven. | Night Shift is strictly excluded from Launch 01. No unattended indexing or background watchers in v0.1. | Enforce Launch 01 boundary: Night Shift is marked as P3 / Post-Release 3 research track in `BACKLOG.md`. | **AWAITING APPROVAL** |
| **CONF-002** | CLI & SDK Scope Boundary | Open Source Spec v1.1 (§4.2, §4.3) vs Stress Backlog v2.0 (Batch 6) | Spec v1.1 mandates a minimal CLI diagnostic surface (`arova doctor`, `arova demo`, manual config) and thin Python client wrapper; Stress Backlog groups expanded SDK/CLI tooling into Batch 6. | Distinguishes lightweight initial developer interface from full client SDK distribution. | Launch 01 implements only the minimal CLI (`arova doctor`, `arova demo`, manual client config output) and thin Python REST client wrapper. Expanded CLI/SDK stability belongs in Batch 6. | Deliver minimal CLI & thin SDK for Launch 01; park Batch 6 expanded interfaces in Future Work backlog. | **AWAITING APPROVAL** |
| **CONF-003** | FFmpeg Packaging & Licensing | Older Backlog notes vs Open Source Spec v1.1 (§8, §1.2) | Older notes proposed bundling an FFmpeg binary; Spec v1.1 and AGENTS rules require auditing exact binary build flags and GPL/LGPL obligations, preferring system FFmpeg. | Shipping a bundled FFmpeg binary without legal/codec build audit risks GPL licensing contagion. | Do not bundle an unverified binary. Require system-installed FFmpeg verified by `arova doctor`, with clear install instructions for Windows, macOS, and Linux. | Document system dependency in `docs/installation.md`, verify presence in `arova doctor`, and document deviation from bundled binary proposal. | **AWAITING APPROVAL** |
| **CONF-005** | MCP Server Toolset: 8 Read-Only Tools vs Opt-in Exports | Spec v1.1 (§3.2, §15.3) vs `mcp_server/server.py` | Spec v1.1 specifies an 8-tool strictly read-only MCP server for AI agents. `mcp_server/server.py` also supports subclip export (`export_video_clip`). | Exposing state-mutating file export to agents violates the strict read-only MCP contract for Launch 01. | Launch 01 AI agent toolset must be strictly read-only by default. `export_video_clip` requires explicit developer opt-in. | Implemented & verified: default server exposes exactly 8 read-only tools; `export_video_clip` is only exposed when `AROVA_ENABLE_MCP_EXPORTS=1` or `--enable-exports` is set. | **AWAITING APPROVAL** |

---

## 3. Unresolved Questions & Implementation Notes

1. **FFmpeg Remediation Guidance:** For systems where `ffmpeg` is missing, should `arova doctor` provide platform-specific package manager instructions (`winget install Gyan.FFmpeg`, `brew install ffmpeg`, `sudo apt install ffmpeg`), or offer a non-destructive helper download script?
   - *Current Recommendation:* Print clear, non-destructive platform-specific copy-paste commands; avoid unattended binary downloads.
2. **Model Cache Location Disclosures:** Spec v1.1 mandates disclosing exact on-disk model cache sizes (`~/.cache/huggingface` and `~/.cache/faster_whisper`).
   - *Current Recommendation:* `arova doctor` inspects and reports these directory sizes without modifying them.

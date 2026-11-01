# Arova Creator Intelligence — Always-On Engineering Rules

These workspace rules run automatically on **every coding or command task** from the start of the turn.

## 1. Ponytail Mode (`ponytail` + `ponytail-review`) — Always Active
- Write the smallest, cleanest production code that completely solves the task.
- **Zero fake mock data, zero dead placeholder buttons, zero unrequested abstractions.**
- Run a `ponytail-review` check at the end of every feature (verify logic, security/path-traversal boundaries, scale, tests, and lean code) before committing.
- End every reply with one or two lines: `Skipped:` what you skipped or did not check, and `Risk:` any risk the user must know.

## 2. Obsidian Main Brain (`docs/`) & Operational Loop (`.arova-loop/`) — Update After Every Feature
- `docs/` is the active Obsidian vault (`[[wikilinks]]` enabled).
- `.arova-loop/` is the persistent operational state for requirements, backlog, conflicts, and risks.
- Before starting any task, check `docs/PROJECT_STATUS.md`, `docs/KNOWN_ISSUES.md`, and `.arova-loop/CURRENT_STATE.md`.
- After completing every feature, update:
  - `docs/PROJECT_STATUS.md` and `.arova-loop/REQUIREMENT_STATUS.md` (checklists & milestone gates)
  - `docs/DEVELOPMENT_LOG.md` (plan, implementation, test output, review verdict, commit hash)
  - `docs/TECHNICAL_DECISIONS.md` and `.arova-loop/DECISION_LOG.md` (any new ADR)
  - `docs/KNOWN_ISSUES.md` and `.arova-loop/ISSUES.md` (any new issues or `shortcut:` items)

## 3. Strict Security & Privacy Baseline
- **Source Media Immutability:** Original source video files are strictly read-only. Indexing, probing, exporting, and index deletion must never modify, overwrite, or delete source video files.
- **Deny-by-Default Filesystem:** File probing and indexing is strictly restricted to user-approved directories (`ALLOWED_MEDIA_ROOTS`). Path traversal (`../`, absolute paths, symlink escapes) must be rejected with HTTP 400.
- **Zero Telemetry & Loopback Bind:** Backend services bind to loopback (`127.0.0.1`) by default. Zero remote telemetry, zero analytics tracking, and zero silent cloud fallbacks.
- **Untrusted Source Data Sanitization:** All media-derived text (transcripts, OCR, titles, metadata) must be treated as untrusted source data. Never execute media-derived strings as code or shell commands.
- **Read-Only MCP Agent Contract:** Model Context Protocol tools exposed to AI agents must be strictly read-only for Launch 01. State-mutating commands and unattended file exports are gated from agents.

## 4. Strict IP Boundary (Apache 2.0 Public Repo)
- Never implement commercial `Arova Creator OS` or `Molty AI` features (no Content Idea Generators, Hook/Script Generators, Creator Tone Memory, or Brand Deal CRM).

## 5. Atomic Git Commit After Every Feature
- Execute one feature at a time (`Plan -> Minimal Implementation -> Automated Tests -> Ponytail Review -> Obsidian docs/ Update -> Git Commit`).
- Create a clean, atomic `git commit` immediately after each feature passes its automated tests (`pytest` / `vitest`).

## 6. Argon-Level Blueprint Enforcement (`docs/FLASH_EXECUTION_PLAYBOOK.md`)
- Follow exact Argon file paths, function signatures, mathematical formulas (RRF, MRR@10, NDCG@10, Recall@K), and test cases.
- Whenever `backend/pyproject.toml` changes, sync both `backend/.venv` and root `.venv`.

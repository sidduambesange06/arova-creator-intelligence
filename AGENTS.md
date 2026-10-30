# Arova Creator Intelligence — Always-On Engineering Rules

These workspace rules run automatically on **every coding or command task** from the start of the turn.

## 1. Ponytail Mode (`ponytail` + `ponytail-review`) — Always Active
- Write the smallest, cleanest production code that completely solves the task.
- **Zero fake mock data, zero dead placeholder buttons, zero unrequested abstractions.**
- Run a `ponytail-review` check at the end of every feature (verify logic, security/path-traversal boundaries, scale, tests, and lean code) before committing.
- End every reply with one or two lines: `Skipped:` what you skipped or did not check, and `Risk:` any risk the user must know.

## 2. Obsidian Main Brain (`docs/`) — Update After Every Feature
- `docs/` is the active Obsidian vault (`[[wikilinks]]` enabled).
- Before starting any task, check `docs/PROJECT_STATUS.md` and `docs/KNOWN_ISSUES.md`.
- After completing every feature, update:
  - `docs/PROJECT_STATUS.md` (checklists & milestone gates)
  - `docs/DEVELOPMENT_LOG.md` (plan, implementation, test output, review verdict, commit hash)
  - `docs/TECHNICAL_DECISIONS.md` (any new ADR)
  - `docs/KNOWN_ISSUES.md` (any new issues or `shortcut:` items)

## 3. TinyFish / Web Benchmark Connector (`tinyfish-connector`) — Active on External Fetch Tasks
- Core video indexing, transcription, and hybrid retrieval remain **100% local-first**.
- When external benchmark metadata, public evaluation references, or web documentation is required, use the workspace `tinyfish-connector` skill (`.agents/skills/tinyfish-connector/SKILL.md`) or `search_web` without leaking private keys or commercial IP.

## 4. Strict IP Boundary (Apache 2.0 Public Repo)
- Never implement commercial `Arova Creator OS` or `Molty AI` features (no Content Idea Generators, Hook/Script Generators, Creator Tone Memory, or Brand Deal CRM).

## 5. Atomic Git Commit After Every Feature
- Execute one feature at a time (`Plan -> Minimal Implementation -> Automated Tests -> Ponytail Review -> Obsidian docs/ Update -> Git Commit`).
- Create a clean, atomic `git commit` immediately after each feature passes its automated tests (`pytest` / `vitest`).

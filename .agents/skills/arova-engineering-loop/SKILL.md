---
name: arova-engineering-loop
description: Orchestrates the Plan -> Minimal Implementation -> Automated Tests -> Ponytail Review -> Obsidian docs/ Update -> Git Commit cycle for Arova Creator Intelligence.
---

# Arova Engineering Loop Skill

## Purpose
Drives continuous feature delivery with zero regressions, strict test evidence, and lean production code.

## The 6-Step Loop
1. **Plan:** Read task requirements, affected files, tests, and dependencies. Keep scope minimal.
2. **Minimal Implementation:** Write clean production code directly solving the task. Zero fake mocks, zero unused wrappers.
3. **Automated Tests:** Execute `pytest backend/tests -v` and `npm test --prefix frontend`. Verify 100% pass rate.
4. **Ponytail Review:** Verify logic correctness, security/traversal checks, performance under load, and code lean-ness.
5. **Obsidian Sync:** Update `docs/PROJECT_STATUS.md`, `DEVELOPMENT_LOG.md`, `TECHNICAL_DECISIONS.md`, and `KNOWN_ISSUES.md`.
6. **Atomic Git Commit:** Commit with a conventional semantic message describing the verified deliverable.

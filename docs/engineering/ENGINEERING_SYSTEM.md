# Arova Engineering System — Unified Operating Loop

**Scope:** Durable engineering operating procedure for Arova Creator Intelligence (Apache 2.0 open-source repository).  
**Last Updated:** 2026-11-20  
**Operational State:** `.arova-loop/` | **Main Brain:** `docs/` Obsidian Vault

---

## 1. Installed & Referenced Skill Sources (Verified 2026-11-20)

| Source | Status in Environment | Role in Unified Loop |
|---|---|---|
| **Matt Pocock Skills** (`mattpocock-skills`: `diagnosing-bugs`, `tdd`, `codebase-design`, `domain-modeling`, `engineering-code-review`, `grilling`) | **Installed** (`C:\Users\Siddhu Ambesanage\.gemini\config\plugins\mattpocock-skills`) | Tight red-capable feedback loops, behavioral tests, deep module boundaries, domain contracts, and Standards+Spec review |
| **Ponytail** (`ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`) | **Installed** (`C:\Users\Siddhu Ambesanage\.gemini\config\plugins\ponytail`) | Smallest complete root-cause change, zero unrequested abstractions, final correctness/security/simplicity review, `Skipped:`/`Risk:` footer |
| **Arova Workspace Skills** (`arova-engineering-loop`, `arova-obsidian-sync`, `arova-project-management`, `arova-release-gate`) | **Installed** (`.agents/skills/`) | Traceability, Obsidian vault synchronization, release-gate hygiene, strict IP & security baseline |
| **Superpowers** (`github.com/obra/superpowers`: `systematic-debugging`, `verification-before-completion`) | **Available in Marketplace** (`antigravity-plugins-partners/plugin/superpowers`, not yet installed locally; core procedures applied directly as documented fallback) | Iron laws: no fixes without root-cause investigation; 3-strike stop-and-rethink brake; no completion claims without fresh verification output |
| **Frontend Design** (Cinematic Instrument design system) | **Repo standard** (`docs/engineering/STITCH_INTEGRATION_MAP.md`, `FRONTEND_BACKEND_PARITY.md`) | Preserves `#080B12` / `#0B1019` / `#111827` / `#172235` / `#243149` / `#9B8CFF` / `#51DCC8` palette, honest states, zero fake data or dead controls |

---

## 2. One Unified Engineering Loop (No Competing Ceremonies)

Every feature, stabilization repair, or performance optimization follows **one single sequence**:

1. **Recover Real State & Protect Data**
   - Inspect live Git state, running processes/ports, active DB path, and free disk space (`C:` vs `D:`).
   - Never run mutation tests against the user's live database; take a verified SQLite online backup before any schema/DB work.
2. **Build a Tight Feedback Loop & Reproduce (`diagnosing-bugs` + `systematic-debugging`)**
   - Reproduce the exact user symptom before proposing edits (failing test, API call, or isolated Chrome CDP check).
   - Trace the full path across boundaries and write a falsifiable root-cause hypothesis (`With input/state X, code path Y fails with Z because ...`).
   - **3-Strike Brake:** If 3 consecutive fix attempts fail to move the signal, STOP patching and re-evaluate the architecture/hypothesis.
3. **Measure Before Optimizing (Performance Changes)**
   - Capture reproducible cold and warm timings (`n >= 10` warm iterations) on identical hardware/data before modifying code.
   - Set explicit target budgets and optimize the measured bottleneck first without relaxing security, consent, or correctness.
4. **Failing Regression Test at a Stable Seam (`tdd`)**
   - Keep working legacy code intact; add the smallest behavioral regression test that fails on the bug (or verifies the new contract) before applying the fix.
5. **Smallest Complete Root-Cause Fix (`ponytail` + `codebase-design`)**
   - Reuse existing services, seams, and contracts. Zero fake data, zero dead controls, zero swallowed errors, zero silent fallbacks.
6. **Fresh Verification Before Completion (`verification-before-completion`)**
   - Run targeted tests, then full backend/MCP tests, frontend Vitest + production build, live browser verification where applicable, and `scripts/system_health_audit.py`.
   - Read raw outputs and exit codes; historical passes never substitute for current verification.
7. **Final Quality & Security Review (`ponytail-review` + `engineering-code-review`)**
   - Audit logic, trust boundaries (auth, Host/Origin, path traversal, read-only SQLite, source media immutability), scale/latency, and diff minimality.
8. **Obsidian Sync & Atomic Local Commit (`arova-obsidian-sync`)**
   - Update `docs/`, `.arova-loop/`, and relevant `reports/product-acceptance/` artifacts; create an explicit, atomic local `git commit` (never commit secrets, audio/video binaries, or model weights; never push/merge without authorization).

---

## 3. Overlap & Precedence Rules

- **Precedence:** Explicit current user instructions > `AGENTS.md` security/IP baseline > this unified loop > individual skill templates.
- **One Ceremony:** Never run separate Matt Pocock and Superpowers planning/test loops for the same change; use the single 8-step loop above.
- **No Destructive Rewrites:** Do not discard working existing code merely because it predates TDD; write a regression reproducer and repair in place.

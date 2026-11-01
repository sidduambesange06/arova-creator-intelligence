---
name: arova-project-management
description: Autonomous project management and work breakdown control for Arova Creator Intelligence. Manages scope, requirement traceability matrix, backlog prioritization (P0-P3), source conflict resolution, and dependency tracking.
---

# Arova Project Management Skill

## Purpose
Enforces rigorous project management for Arova Creator Intelligence according to Open Source Spec v1.1 and the autonomous loop operational state in `.arova-loop/`.

## Core Responsibilities
1. **Source Hierarchy Enforcement:**
   - Priority 1: Open Source Spec v1.1 (`AROVA_CREATOR_INTELLIGENCE_OPEN_SOURCE_SPEC_AND_LAUNCH_01.md`).
   - Priority 2: Actual repository source code and passing automated tests.
   - Priority 3: Stress-tested backlog v2.0.
   - Strictly exclude unapproved scope (Night Shift is deferred post-Release 3; no commercial Creator OS).
2. **Backlog Prioritization:**
   - **P0:** Critical security, data integrity, and release blockers.
   - **P1:** Launch-critical approved functionality (Launch 01).
   - **P2:** Non-blocking post-launch improvements (held until v0.1 ships).
   - **P3:** Gated research tracks (post-Release 3).
3. **Traceability Maintenance:**
   - Maintain `.arova-loop/REQUIREMENT_STATUS.md` (`REQ-001` through `REQ-035+`).
   - Ensure every implemented feature links to observable acceptance criteria and automated test evidence.
4. **Conflict Resolution:**
   - Record and resolve scope conflicts in `.arova-loop/SOURCE_CONFLICTS.md` with explicit user approval gates.

---
name: arova-release-gate
description: Enforces release criteria and verification checks for Arova Creator Intelligence before public distribution, tagging, or milestone sign-off.
---

# Arova Release Gate Skill

## Purpose
Validates that all release requirements from Open Source Spec v1.1 (§11) are satisfied with reproducible automated evidence before any public release or version tag.

## Mandatory Release Checks
1. **Source Immutability:** Confirm source video files remain byte-for-byte identical after ingestion, search, and index deletion.
2. **Test Suite Execution:** 100% passing tests across backend (`pytest backend/tests -v`) and frontend (`npm test --prefix frontend`).
3. **Production Build:** `npm run build --prefix frontend` succeeds without TypeScript or bundling errors.
4. **Read-Only MCP Contract:** Verify FastMCP server exposes only the 8 approved read-only tools to agents without state mutation.
5. **Security & Privacy Baseline:** Verify loopback default (`127.0.0.1`), deny-by-default filesystem roots, and zero telemetry.
6. **Licensing & SBOM:** Verify Apache-2.0 compliance, root `LICENSE` and `NOTICE` presence, and dependency license audit.
7. **No Fabricated Claims:** Ensure all README claims reflect verified status in `docs/FEATURE_STATUS.md`.


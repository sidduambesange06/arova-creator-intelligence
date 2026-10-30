---
name: tinyfish-connector
description: >-
  External web metadata and public benchmark fetcher using TinyFish Web Agent API
  (or local fallback) for Arova Creator Intelligence. Activate when fetching public
  video benchmark manifests, external documentation, or web metadata during development.
---

# TinyFish Web Agent Connector

Use this skill whenever a task requires fetching external public benchmark manifests,
open-source video metadata, or web specifications while keeping `arova-creator-intelligence`
100% local-first for media indexing.

## Rules
1. **Local-First Boundary:** Never send local user video files, transcripts, or paths to external web endpoints.
2. **Usage:**
   - If `TINYFISH_API_KEY` is configured in `.env`, invoke `https://mino.ai/v1/automation/run-sse` (TinyFish Web Agent endpoint) with `{ "url": "<target_url>", "goal": "<extraction_goal>" }`.
   - If `TINYFISH_API_KEY` is not set, fall back cleanly to built-in `search_web` or deterministic local benchmark fixtures in `sample_data/`.
3. **Log Findings:** Record any external benchmark sources in `docs/TECHNICAL_DECISIONS.md`.

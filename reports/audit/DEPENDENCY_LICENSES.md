# Arova Creator Intelligence — Dependency License Audit

**Document Class:** Open Source License & Compliance Audit
**Root License:** Apache License 2.0 (`LICENSE`, `NOTICE`)
**Audit Date:** 2026-11-03

---

## 1. Compliance Executive Summary

All core software components, libraries, and frameworks distributed within Arova Creator Intelligence operate under permissive open-source licenses compatible with the Apache-2.0 root distribution:
- **Zero Proprietary / Commercial Code:** No proprietary modules included.
- **Zero AGPL / Copyleft Contagion in Default Package:** No AGPL runtime dependencies.
- **External System Dependencies:** FFmpeg and ffprobe are consumed as external host system CLI binaries (or via `imageio-ffmpeg` permissive binaries), avoiding binary bundling compliance ambiguities.

---

## 2. Python Backend Dependencies Audit

### 2.1 Base Installation Dependencies (`backend/pyproject.toml`)

| Package | License Type | Compliance Assessment | Notes |
|---|---|---|---|
| `fastapi` | MIT | Fully Compatible | Core REST OpenAPI framework |
| `uvicorn` | BSD-3-Clause | Fully Compatible | ASGI server implementation |
| `pydantic` | MIT | Fully Compatible | Data validation & schemas |
| `pydantic-settings` | MIT | Fully Compatible | Environment configuration |
| `sqlalchemy` | MIT | Fully Compatible | Relational ORM and SQLite interface |
| `alembic` | MIT | Fully Compatible | Database schema migrations |
| `imageio-ffmpeg` | BSD-2-Clause | Fully Compatible | FFmpeg binary resolution wrapper |
| `mcp` | MIT | Fully Compatible | Official Model Context Protocol SDK |

### 2.2 Development Dependencies

| Package | License Type | Compliance Assessment | Notes |
|---|---|---|---|
| `pytest` | MIT | Fully Compatible | Test runner |
| `httpx` | BSD-3-Clause | Fully Compatible | Async HTTP client for API tests |

### 2.3 Optional AI Extras (Opt-In Only)

| Package | Optional Group | License Type | Notes |
|---|---|---|---|
| `sentence-transformers` | `ai` | Apache-2.0 | Optional dense embeddings and Cross-Encoder re-ranking |
| `faster-whisper` | `asr` | MIT | Optional offline speech recognition runtime |
| `google-genai` | `cloud` | Apache-2.0 | Optional Google Gemini cloud SDK (requires explicit consent) |

---

## 3. Node.js Frontend Dependencies Audit (`frontend/package.json`)

| Package | License Type | Compliance Assessment | Notes |
|---|---|---|---|
| `react` | MIT | Fully Compatible | UI library |
| `react-dom` | MIT | Fully Compatible | DOM renderer |
| `vite` | MIT | Fully Compatible | Frontend bundler |
| `typescript` | Apache-2.0 | Identical License | TypeScript language tooling |
| `tailwindcss` | MIT | Fully Compatible | CSS styling |
| `lucide-react` | ISC (Permissive) | Fully Compatible | SVG icons |
| `vitest` | MIT | Fully Compatible | Testing runner |
| `@testing-library/react` | MIT | Fully Compatible | React component testing utilities |

---

## 4. Media & Test Fixtures Audit
- **Sample Media:** Synthetic sample media in `sample_data/` is generated locally using standard `color` and `sine` test patterns via FFmpeg or licensed under CC0 Public Domain. No copyrighted third-party videos are included.
- **Weights & Models:** Default installation requires zero pre-downloaded model weights. Optional embedding models (`all-MiniLM-L6-v2`, `ms-marco-MiniLM-L-6-v2`) operate under Apache-2.0.

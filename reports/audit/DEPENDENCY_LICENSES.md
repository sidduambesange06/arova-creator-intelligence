# Arova Creator Intelligence — Dependency License Audit

**Document Class:** Open Source License & Compliance Audit  
**Authority:** Open Source Spec v1.1 (§8)  
**Root License:** Apache License 2.0 (`LICENSE`, `NOTICE`)  
**Audit Date:** 2026-11-01  

---

## 1. Compliance Executive Summary
All core software components, libraries, and frameworks distributed within Arova Creator Intelligence operate under permissive open-source licenses compatible with the Apache-2.0 root distribution:
- **Zero Proprietary / Commercial Code:** No proprietary modules included.
- **Zero AGPL / Copyleft Contagion in Default Package:** No AGPL runtime dependencies.
- **External System Dependencies:** FFmpeg and ffprobe are consumed as external host system CLI binaries, avoiding binary bundling compliance ambiguities.

---

## 2. Python Backend Dependencies Audit

| Package | License Type | Compliance Assessment | Notes |
|---|---|---|---|
| `fastapi` | MIT | Fully Compatible | Core REST OpenAPI framework |
| `uvicorn` | BSD-3-Clause | Fully Compatible | ASGI server implementation |
| `sqlalchemy` | MIT | Fully Compatible | ORM and SQL toolkit |
| `pydantic` | MIT | Fully Compatible | Data validation |
| `chromadb` | Apache-2.0 | Identical License | Vector database |
| `sentence-transformers` | Apache-2.0 | Identical License | Dense embeddings and Cross-Encoder |
| `torch` (PyTorch) | BSD-3-Clause | Fully Compatible | Neural inference runtime |
| `faster-whisper` | MIT | Fully Compatible | Local offline ASR engine |
| `ctranslate2` | MIT | Fully Compatible | Fast inference runtime for whisper |
| `scenedetect` | BSD-3-Clause | Fully Compatible | Video scene cut detection |
| `pillow` | HPND (MIT-style) | Fully Compatible | Imaging and thumbnail generation |
| `numpy` | BSD-3-Clause | Fully Compatible | Numerical calculations |
| `mcp` (FastMCP) | MIT | Fully Compatible | Official Model Context Protocol SDK |
| `pytest` | MIT | Fully Compatible | Test suite |

---

## 3. Node.js Frontend Dependencies Audit

| Package | License Type | Compliance Assessment | Notes |
|---|---|---|---|
| `react` | MIT | Fully Compatible | UI library |
| `react-dom` | MIT | Fully Compatible | DOM renderer |
| `vite` | MIT | Fully Compatible | Frontend bundler |
| `typescript` | Apache-2.0 | Identical License | TypeScript language tooling |
| `tailwindcss` | MIT | Fully Compatible | CSS styling |
| `lucide-react` | ISC (Permissive) | Fully Compatible | SVG icons |
| `vitest` | MIT | Fully Compatible | Testing runner |
| `@testing-library/react` | MIT | Fully Compatible | Testing utilities |

---

## 4. Media & Codec Audit
- **Sample Media:** Synthetic sample media in `sample_data/` is generated locally using standard `color` and `sine` test patterns via FFmpeg or licensed under CC0 Public Domain. No copyrighted third-party videos are included.
- **Weights & Models:** Embedding models (`all-MiniLM-L6-v2`, `ms-marco-MiniLM-L-6-v2`) are licensed under Apache-2.0.


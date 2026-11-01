# Arova Creator Intelligence — Technical Dependencies Map

**Document Authority:** Open Source Spec v1.1 (§8)  
**Status:** Managed Operational State  

---

## 1. System & Runtime Dependencies

| Component | Minimum Version | Required By | Licensing | Check / Diagnostic |
|---|---|---|---|---|
| **Python** | 3.11+ | Backend, MCP Server, Evaluation Harness | PSF License | `python --version` |
| **Node.js** | 20+ | Frontend React Workstation | MIT | `node --version` |
| **FFmpeg / ffprobe** | 4.4+ (system) | Media Probing, Audio Extraction, Keyframes, Subclips | LGPL / GPL depending on build | `ffmpeg -version`, `arova doctor` |
| **SQLite with FTS5** | 3.35+ | Metadata Store, Segment Storage, BM25 Lexical Search | Public Domain | Built into Python `sqlite3` |

---

## 2. Python Package Dependencies

| Package | Shipped Version | Primary Purpose | License |
|---|---|---|---|
| `fastapi` | 0.115.8 | Core REST OpenAPI Server | MIT |
| `uvicorn` | 0.34.0 | ASGI Server | BSD-3-Clause |
| `sqlalchemy` | 2.0.38 | ORM & Database Sessions | MIT |
| `pydantic` | 2.10.6 | Data Validation & Schemas | MIT |
| `mcp` | 1.3.0 | Official Model Context Protocol FastMCP Server | MIT |
| `chromadb` | 0.6.3 | Vector Database for Dense Chunks | Apache-2.0 |
| `sentence-transformers` | 3.4.1 | Dense Vectors & Cross-Encoder Re-Ranking | Apache-2.0 |
| `torch` | 2.6.0+cpu | PyTorch Local Inference (CPU/CUDA) | BSD-3-Clause |
| `faster-whisper` | 1.1.1 | Local Offline Speech ASR | MIT |
| `scenedetect` | 0.6.5.2 | Video Scene Boundary Detection | BSD-3-Clause |
| `pillow` | 11.1.0 | Image & Thumbnail Processing | MIT-CMU |
| `numpy` | 2.2.3 | Array Computations & Vector Normalization | BSD-3-Clause |
| `pytest` | 9.2.0 | Testing Harness | MIT |

---

## 3. Frontend Package Dependencies

| Package | Shipped Version | Primary Purpose | License |
|---|---|---|---|
| `react` | 18.3.1 | UI Framework | MIT |
| `react-dom` | 18.3.1 | DOM Rendering | MIT |
| `vite` | 5.4.21 | Build Tool & Dev Server | MIT |
| `typescript` | 5.7.2 | Static Type Checking | Apache-2.0 |
| `tailwindcss` | 3.4.17 | Utility-First CSS | MIT |
| `lucide-react` | 0.475.0 | SVG Icons | ISC |
| `vitest` | 2.1.9 | Frontend Unit Testing | MIT |
| `@testing-library/react` | 16.2.0 | Component DOM Testing | MIT |


# Arova Creator Intelligence — Security Control Gap Assessment

**Document Class:** Security & Threat Model Audit  
**Authority:** Open Source Spec v1.1 (§7.2, §7.3)  
**Audit Date:** 2026-11-01  

---

## 1. Threat Matrix & Control Gap Analysis

| Threat / Attack Vector | Target Area | Current Control Implementation | Gap / Residual Risk | Recommended Remediation | Severity |
|---|---|---|---|---|---|
| **Path Traversal / Arbitrary File Access** | Media Probing, Video Streaming, Clip Export | `validate_media_path` checks canonical paths against `ALLOWED_MEDIA_ROOTS`. Explicit `HTTPException(400)` on breach. | `ALLOWED_MEDIA_ROOTS` currently defaults to `.,..` for sample imports. | In production deployments, restrict default to dedicated media folder (e.g. `./media`). | Low |
| **Source Media Corruption / Deletion** | Ingestion, Deletion APIs | Source files are opened read-only. Index deletion unlinks database records and thumbnails only. | None identified. Verified by tests. | Maintain automated source hash verification in release gates. | Negligible |
| **Untrusted Media Content / Prompt Injection** | Transcripts, OCR text, Video Titles | Grounded Q&A treats transcripts as quoted context; does not evaluate text as instructions. | Complex multi-turn LLMs interacting via MCP might interpret text as system instructions. | Add explicit system prompt boundary markers `<<<UNTRUSTED_VIDEO_TRANSCRIPT>>>` in MCP responses. | Medium |
| **Loopback / Unauthenticated Network Exposure** | FastAPI Server, MCP STDIO | FastAPI defaults to `127.0.0.1:8000`. FastMCP server operates over local STDIO. | If user runs `uvicorn --host 0.0.0.0`, API is exposed to LAN without auth. | Add startup warning if binding to non-loopback host without an API key configured. | Low |
| **Model Poisoning & Remote Code Execution** | SentenceTransformers / PyTorch | Uses standard Hugging Face model IDs with safetensors; no untrusted pickle downloads. | Direct model downloads from Hugging Face could fail if offline. | Pinned model weights with deterministic offline fallback. | Low |
| **Resource Exhaustion (Denial of Service)** | FFmpeg probing & scene detection | Bounded timeouts and segment lengths. | Extremely large media files (4K 60fps > 50 GB) could cause high RAM consumption. | Add max file size and timeout configuration in `.env`. | Low |

---

## 2. Assessment Summary
The core local-first architecture satisfies the required Launch 01 security baseline:
- Source media immutability is guaranteed.
- Loopback-only binding is enforced by default.
- Zero telemetry and zero remote data leakage.
- AI agent access via FastMCP is restricted to read-only retrieval tools.


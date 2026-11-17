# ADR-0007: BYO-AI Provider Gateway, Multi-Model Routing, and Privacy Boundaries

**Status:** Accepted  
**Date:** 2026-11-09  
**Author:** Principal Software Architect & Antigravity Autonomous Loop  
**Scope:** AI Provider Gateway, Capability Routing, Consent Gating, and Provenance Logging (Roadmap Step 6)

---

## 1. Context and Problem Statement

Arova Creator Intelligence requires flexible multimodal AI reasoning (grounded video Q&A, chaptering, summarization) across heterogeneous environments:
1. **Fully offline workstations:** Zero network egress, zero token costs, deterministic extractive grounded answers.
2. **Local AI runtimes:** Self-hosted OpenAI-compatible servers (Ollama, vLLM, LM Studio) on local loopback (`http://localhost:11434/v1`).
3. **Bring-Your-Own-Key (BYOK) Cloud Providers:** Google Gemini, OpenAI, and Anthropic Claude.

Prior to Step 6, external AI invocation was coupled directly to Google Gemini SDK inside `summary_service.py` with binary `AI_REMOTE_CONSENT` gating. There was no unified provider abstraction, no model catalog discovery, no credentials verification endpoint, no standardized support for OpenAI or Anthropic models, and no durable audit logging of remote model calls in the database.

---

## 2. Decision and Architecture

We introduce the **BYO-AI Provider Gateway** (`backend/app/ai/providers/gateway.py`) with a clean provider-neutral protocol layer:

```
[FastAPI Route / Agent Client]
             │
             ▼
   [AIProviderGateway] ───────────────► [AIConsent & ExecutionProfile Gate]
             │                                       │
             ├───────────────┬───────────────┬───────┴───────┐
             ▼               ▼               ▼               ▼
      [LocalExtractive]   [Gemini]        [OpenAI/Ollama] [Anthropic]
         (100% Offline)   (GoogleGenAI)   (REST /v1/chat) (Messages REST)
             │               │               │               │
             └───────────────┴───────┬───────┴───────────────┘
                                     │
                                     ▼
                            [AIRun Audit Record]
                       (SHA-256 prompt hash, zero secrets)
```

### 2.1 Core Architectural Principles
1. **Zero External Dependency Overhead:**
   - Adapters for OpenAI and Anthropic are implemented using Python standard library `urllib.request` / `json`, eliminating the need for heavyweight SDK dependencies (`openai`, `anthropic`).
   - Google Gemini utilizes `google-genai` if installed, with automatic graceful HTTPS REST fallback.
2. **Local Loopback Detection:**
   - Endpoints pointing to `localhost`, `127.0.0.1`, `::1`, or `0.0.0.0` are classified as `ExecutionLocation.LOCAL`. They do not trigger remote egress alerts and can execute without API keys (e.g. for local Ollama).
3. **Five-Gate Consent Precedence:**
   A remote provider call is permitted only when **all** of the following conditions pass:
   - `provider_id != "local"` (Local provider is always permitted).
   - `ExecutionProfile` is not `FULLY_OFFLINE_NO_AI` or `LOCAL_AI`.
   - `RootPolicy` is not `LOCAL_ONLY`.
   - Explicit user consent exists: request parameter `consent_remote_ai=True`, system configuration `settings.AI_REMOTE_CONSENT=True`, or active, unexpired, unrevoked `AIConsent` database record matching provider & capability.
   - If consent is not granted, the gateway automatically falls back to `LocalExtractiveProvider` with `remote_egress=False`.
4. **Credential Masking & Security:**
   - Keys are masked (`sk-...abcd`) in all logs, exceptions, and audit records.
   - Zero storage of plaintext API keys in the database.
5. **Durable Provenance via `AIRun`:**
   - Every AI call records an `AIRun` entity with deterministic SHA-256 `prompt_hash`, provider ID, model name, execution location (`local` vs `remote`), data categories egressed, input refs, and optional consent FK.

---

## 3. Supported Capabilities and Model Catalog

| Capability | Local Provider | Google Gemini | OpenAI / Compatible | Anthropic |
|---|---|---|---|---|
| `llm_qa` | `grounded-extractive-local` | `gemini-2.5-flash`, `gemini-2.0-flash` | `gpt-4o-mini`, `gpt-4o`, custom | `claude-3-5-haiku-20241022`, `claude-3-5-sonnet-20241022` |
| `summarization` | `extractive-grounded-local` | `gemini-2.5-flash` | `gpt-4o-mini`, custom | `claude-3-5-haiku-20241022` |
| `asr` | `faster-whisper` (offline) | — | — | — |
| `embeddings` | `all-MiniLM-L6-v2` / token n-gram | — | — | — |
| `reranking` | `cross-encoder/ms-marco` | — | — | — |

---

## 4. REST API Surface (`/api/v1/ai/`)

- `GET /api/v1/ai/providers`: Catalog of registered providers, supported capabilities, and models.
- `POST /api/v1/ai/providers/verify`: Non-destructive credential and connectivity verification.
- `GET /api/v1/ai/consents`: List recorded AI consents.
- `POST /api/v1/ai/consents`: Grant an explicit scoped AI consent record.
- `DELETE /api/v1/ai/consents/{id}`: Immediately revoke an existing consent record.
- `GET /api/v1/ai/runs`: Paginated `AIRun` audit trail with prompt hashes and data categories.

---

## 5. Consequences & Verification

- **Backwards Compatibility:** Existing endpoints (`/api/v1/ai/ask`, `/api/v1/ai/summarize`) and test suites (`test_prompt_injection_redteam.py`, `test_ai_consent_boundary.py`, `test_clips_and_summary.py`) remain 100% compatible.
- **Verification:** 14 unit tests in `backend/tests/unit/test_byo_ai_gateway.py` covering provider discovery, credential validation, local fallback, consent rules, network fault injection, and REST endpoints. Full test suite: 225/225 passed.


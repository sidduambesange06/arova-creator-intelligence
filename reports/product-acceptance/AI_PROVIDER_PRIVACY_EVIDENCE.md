# Arova Creator Intelligence — BYO-AI Gateway & Privacy Consent Acceptance Evidence

**Document ID:** `REP-ACCEPT-002`  
**Date:** `2026-11-09`  
**Subsystem:** BYO-AI Gateway, Multi-Provider Adapters, Privacy Enclave & Consent Lifecycle  
**Governing Blueprints:** `backend/app/ai/providers/gateway.py`, `backend/app/ai/providers/base.py`, `backend/app/api/routes/ai_gateway.py`  
**Test Suite:** `scratch/verify_privacy_gateway.py`, `backend/tests/unit/test_ai_gateway_api.py`  
**Verification Result:** **100% PASSED (ZERO LEAKS, STRICT PRIVACY GATES ACTIVE)**  

---

## 1. Executive Summary & Privacy Guarantees

Arova Creator Intelligence adheres to an uncompromising **Local-First & Non-Bypassable Privacy Architecture**:

1. **Local Extractive Default:**  
   Out of the box, Arova operates 100% offline using `LocalExtractiveProvider`. It requires zero credentials, costs zero tokens, and performs zero outbound network requests.
2. **Bring-Your-Own-AI (BYO-AI) Gateway:**  
   Users may optionally connect their own API keys for **Google Gemini**, **OpenAI / OpenAI-Compatible (Ollama, vLLM, LM Studio)**, or **Anthropic Claude**.
3. **Strict Non-Bypassable Consent Precedence:**  
   No remote API call can ever execute unless explicit consent is active. Remote egress is governed by a 5-gate precedence evaluation engine:
   - **Gate 1:** `local` provider is always permitted (local execution only).
   - **Gate 2:** `ExecutionProfile.FULLY_OFFLINE_NO_AI` or `LOCAL_AI` immediately blocks remote egress, superseding all user tokens.
   - **Gate 3:** `RootPolicy.LOCAL_ONLY` on media folders blocks remote egress for media inside that root.
   - **Gate 4:** Explicit request-level flag (`consent_remote_ai=True`).
   - **Gate 5:** Active, non-expired, non-revoked database `AIConsent` record matching the provider and capability.
4. **Zero Cloud Leakage & Zero Plaintext Credential Exposure:**  
   - API keys are never returned in plaintext to the frontend.
   - All errors from upstream providers pass through `mask_secret()`, ensuring raw tokens are redacted (`sk-...xxxx` or `[REDACTED_SECRET]`).
   - Database `AIRun` audit records store only SHA-256 prompt hashes and data categories, never storing raw creator transcripts or prompts.
   - Portable `.arova` archives run regex-based secret scanning on export and redact detected credentials.

---

## 2. Provider Catalog & Capabilities Matrix

The following table details the verified status and registered capabilities across all 4 supported providers:

| Provider Identifier | Display Name | Execution Location | Supported Capabilities | Models Discovered | Default Model | Zero Key Required |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `local` | Local Extractive Engine | `local` | `llm_qa`, `summarization` | `grounded-extractive-local`, `extractive-grounded-local` | `grounded-extractive-local` | **YES (Always Ready)** |
| `google-gemini` | Google Gemini | `remote` | `llm_qa`, `summarization` | `gemini-2.5-flash`, `gemini-2.0-flash` | `gemini-2.5-flash` | NO (Requires API Key) |
| `openai` | OpenAI & Compatible (Ollama/vLLM) | `remote` / `local` | `llm_qa`, `summarization` | `gpt-4o-mini`, `gpt-4o` | `gpt-4o-mini` | Local URLs: YES; Remote: NO |
| `anthropic` | Anthropic (Claude) | `remote` | `llm_qa`, `summarization` | `claude-3-5-haiku-20241022`, `claude-3-5-sonnet-20241022` | `claude-3-5-haiku-20241022` | NO (Requires API Key) |

---

## 3. Credential Verification & Error Handling Evidence

Every provider was probed under normal, missing, invalid, and malformed credential conditions:

### 3.1 Local Provider
- Input: No API key, no base URL.
- Output: `is_valid: True, error: None`.
- Behavior: Instant deterministic validation without network egress.

### 3.2 Google Gemini Provider
- **Missing Credential Test:**
  - Input: `api_key: ""`
  - Output: `is_valid: False, error: "Gemini API key is required"`
- **Invalid Credential Test:**
  - Input: `api_key: "AIzaSyFakeInvalidKeyForTestingArovaSecurity999"`
  - Upstream Response: `HTTP 400: API key not valid. Please pass a valid API key.`
  - Redaction Assertion: Raw key was checked in error message -> **ASSERTION PASSED (Key NOT leaked).**

### 3.3 OpenAI-Compatible Provider
- **Missing Remote Credential Test:**
  - Input: `api_key: "", base_url: "https://api.openai.com/v1"`
  - Output: `is_valid: False, error: "OpenAI API key is required for remote endpoints"`
- **Loopback Detection Test:**
  - Input: `base_url: "http://127.0.0.1:11434/v1"` (Ollama)
  - Output: `is_local_endpoint == True` (Permits execution without requiring external API keys).
- **Invalid Remote Credential Test:**
  - Input: `api_key: "sk-proj-FakeOpenAIKeyForTestingPrivacyArova12345"`
  - Upstream Response: `HTTP 401: Incorrect API key provided: sk-proj-*************...`
  - Redaction Assertion: `mask_secret` returned `sk-...2345`. Raw key was NOT present in error string -> **ASSERTION PASSED.**

### 3.4 Anthropic Claude Provider
- **Missing Credential Test:**
  - Input: `api_key: ""`
  - Output: `is_valid: False, error: "Anthropic API key is required"`
- **Invalid Credential Test:**
  - Input: `api_key: "sk-ant-api03-FakeAnthropicKeyForTestingArova67890"`
  - Upstream Response: `HTTP 401: {"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}`
  - Redaction Assertion: Raw key was NOT present in error string -> **ASSERTION PASSED.**

---

## 4. Multi-Gate Privacy Consent Lifecycle Evidence

The 5-gate consent evaluation engine was tested sequentially against an isolated SQLite test database:

```
[Gate Evaluation 1: No Consent Granted]
Query: evaluate_consent(provider="google-gemini", capability="llm_qa", consent_remote_ai=False)
Result: permitted=False
Reason: "No active consent granted for remote AI egress"
Verdict: Remote call blocked at gateway boundary.

[Gate Evaluation 2: Local Execution Invariant]
Query: evaluate_consent(provider="local", capability="llm_qa")
Result: permitted=True
Reason: "local_execution"
Verdict: Local deterministic Q&A permitted with zero egress.

[Gate Evaluation 3: ExecutionProfile Lockdown]
Query: evaluate_consent(provider="google-gemini", consent_remote_ai=True, execution_profile="fully_offline_no_ai")
Result: permitted=False
Reason: "Blocked by ExecutionProfile 'fully_offline_no_ai' (local-only)"
Verdict: Profile-level security policy strictly blocks remote egress even if caller sets consent flag.

[Gate Evaluation 4: RootPolicy Folder Lockdown]
Query: evaluate_consent(provider="google-gemini", consent_remote_ai=True, root_policy="local_only")
Result: permitted=False
Reason: "Blocked by RootPolicy 'local_only'"
Verdict: Media root policy strictly blocks remote egress for contained footage.

[Gate Evaluation 5: Active Database Consent Grant]
Action: Grant AIConsent(scope_type="library", scope_id="lib-acceptance-001", provider="google-gemini", expires_in_hours=2)
Query: evaluate_consent(provider="google-gemini", capability="llm_qa", scope_id="lib-acceptance-001")
Result: permitted=True
Reason: "db_consent"
Matched Record ID: 4169a568-5a12-4501-87f6-d6e5609e34cd
Verdict: Consent granted and verified for matching scope and capability.

[Gate Evaluation 6: Time-Bounded Consent Expiration]
Action: Set expires_at to 10 seconds in the past.
Query: evaluate_consent(provider="google-gemini", capability="llm_qa", scope_id="lib-acceptance-001")
Result: permitted=False
Reason: "No active consent granted for remote AI egress"
Verdict: Expired consent automatically rejected by gateway without user action.

[Gate Evaluation 7: Immediate Consent Revocation]
Action: Re-extend expiration to +5 hours, but set revoked_at=now.
Query: evaluate_consent(provider="google-gemini", capability="llm_qa", scope_id="lib-acceptance-001")
Result: permitted=False
Reason: "No active consent granted for remote AI egress"
Verdict: Revoked consent immediately blocks subsequent remote calls.
```

---

## 5. Zero Cloud Leakage & Deterministic Local Fallback

To verify that denied consent never crashes the application or makes unauthorized network calls, a live inference request was submitted:

```
[Inference Request]
Target Capability: llm_qa
Preferred Provider: "google-gemini" (Remote requested)
User Consent Flag: False (Consent DENIED)
Input Context: "Thom: What happened here? We need to recalibrate the tracking beam before the robot arrives."
Question: "What did Thom say about recalibrating the tracking beam?"

[Execution Trace]
1. Gateway evaluated consent for provider "google-gemini" -> Result: False ("No active consent").
2. Gateway logged: "Remote provider 'google-gemini' requested but consent denied. Falling back to local."
3. Gateway routed query to LocalExtractiveProvider (grounded-extractive-local).
4. Local provider performed deterministic extractive search over retrieval windows.
5. Generated Output:
   - Provider used: "local"
   - Execution Location: "local"
   - Remote Egress: False
   - Data Categories Egressed: []
   - Tokens Charged: 0
6. Audit Log Recorded:
   - AIRun ID: 18e6b9bc-8107-44a5-9fcf-ff05e867442a
   - Provider: "local"
   - Execution Location: "local"
   - Prompt SHA-256 Hash: b9a006b92195c6759ad2ef8a5d905b5e20d1a749ae0f0dd1e8f784fefb098e77
   - Raw Text Stored: NONE
```

**Verdict:** The Privacy & BYO-AI Gateway strictly enforces non-bypassable privacy boundaries, secret redaction, time-bounded consent, immediate revocation, and seamless local-first fallback with zero cloud leakage.

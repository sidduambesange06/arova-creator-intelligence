# Arova Creator Intelligence — Risk Register

**Document Authority:** Open Source Spec v1.1 (§7.3)  
**Status:** Managed Operational State  

---

## Risk Analysis & Mitigation Matrix

| Risk ID | Category | Risk Description | Likelihood | Impact | Severity | Mitigation & Technical Control | Status |
|---|---|---|---|---|---|---|---|
| **RISK-001** | Security | Path Traversal / Arbitrary File Probe via symlink or relative path | Medium | High | **High** | `validate_media_path` resolves and canonicalizes paths, enforcing strict containment within `ALLOWED_MEDIA_ROOTS`. | `MITIGATED` |
| **RISK-002** | Data Integrity | Original Video Media Modification or Unintended Deletion | Low | Critical | **Critical** | Read-only filesystem operations on source media. `DELETE /api/v1/videos/{id}/index` explicitly unlinks only DB records and thumbnails. Source media remains untouched. | `MITIGATED` |
| **RISK-003** | Security | Prompt Injection via Media-Derived Text (Transcripts/OCR) | Medium | Medium | **Medium** | All media-derived text is tagged as untrusted context; no dynamic code execution or command generation from transcript tokens. | `MITIGATED` |
| **RISK-004** | Privacy | Unintended Network Egress / Cloud Data Leakage | Low | High | **High** | Loopback binding by default (`127.0.0.1`); zero telemetry; no silent external model fallbacks. Cloud disclosure clearly stated in documentation. | `MITIGATED` |
| **RISK-005** | Legal | GPL License Contagion from Bundled Binaries | Low | High | **High** | No bundled FFmpeg binary; rely on host system FFmpeg verified via non-destructive `arova doctor`. Clear attribution in `NOTICE`. | `MITIGATED` |
| **RISK-006** | Performance | Heavy ML Model Startup Blocking MCP Discovery | Medium | Medium | **Medium** | FastMCP server uses lazy model loading; tool discovery and inventory listing run in < 100ms without importing PyTorch or Whisper weights. | `MITIGATED` |
| **RISK-007** | Reliability | Missing Weights or Cold Start Failure in Offline Mode | Medium | Medium | **Medium** | Deterministic fallback pipelines for transcription and embeddings when local weights are uninitialized, preventing hard application crashes. | `MITIGATED` |


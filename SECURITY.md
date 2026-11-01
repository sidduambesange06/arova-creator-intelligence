# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x (Launch 01) | :white_check_mark: |
| < 0.1.0 | :x: |

---

## Reporting a Vulnerability

We take the security and privacy of local media processing seriously. If you discover a potential vulnerability in Arova Creator Intelligence, please report it responsibly:

1. **Do not create public GitHub issues** for security vulnerabilities.
2. Send an email to the project maintainers or use GitHub's private vulnerability reporting feature under **Security -> Advisories -> Report a vulnerability**.
3. Include:
   - Type of vulnerability (e.g. path traversal, unauthenticated network exposure, prompt injection via transcript metadata).
   - Step-by-step reproduction instructions and minimal proof-of-concept media if applicable.
   - Impact assessment.
4. Maintainers will acknowledge receipt within 48 hours and provide remediation updates.

---

## Local-First Security & Threat Model Baseline

Arova Creator Intelligence adheres to strict privacy and defense-in-depth principles:
- **Loopback Binding by Default:** The backend service binds exclusively to `127.0.0.1`. It never listens on `0.0.0.0` unless explicitly configured by the user.
- **Source Media Immutability:** Source video files are strictly read-only. Indexing and deleting library indexes never modifies, deletes, or overwrites source files.
- **Deny-by-Default Filesystem:** File probing and ingestion is restricted to directories listed under `ALLOWED_MEDIA_ROOTS`. Path traversal attempts (`../`, URL encoded escapes, symlink escapes) are rejected with HTTP 400.
- **Untrusted Source Text Sanitization:** All transcripts, OCR text, file titles, and metadata are treated as untrusted source data. They are never executed as code or shell commands.
- **Read-Only MCP Agent Boundary:** AI agents connecting via FastMCP STDIO are limited strictly to read-only retrieval tools. Exporting subclips or mutating state requires explicit developer opt-in.
- **Zero Remote Telemetry:** No analytics tracking, telemetry pings, or silent cloud fallbacks.

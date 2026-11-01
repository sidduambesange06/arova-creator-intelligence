# Contributing to Arova Creator Intelligence

Thank you for your interest in contributing! Arova Creator Intelligence is an open-source, local-first video intelligence engine licensed under the Apache License 2.0.

---

## Code of Conduct
All contributors and maintainers are expected to adhere to our [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## Development Environment Setup

### Prerequisites
- Python 3.11+
- Node.js 20+ & npm
- FFmpeg and ffprobe (installed and available on system `PATH`)

### Backend Setup
```bash
git clone https://github.com/sidduambesange06/arova-creator-intelligence.git
cd arova-creator-intelligence

# Using Python venv
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\Activate.ps1
pip install -e backend/

# Run system health diagnostics
python -m arova doctor
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## Running Automated Tests

Always run both backend and frontend test suites before submitting a pull request:

```bash
# Backend, CLI & FastMCP tests
pytest backend/tests mcp_server/tests -v

# Frontend tests & production build check
npm test --prefix frontend -- --run
npm run build --prefix frontend
```

---

## Engineering Guidelines (Ponytail Mode)

1. **Smallest Complete Change:** Solve problems with the least new code. No dead abstractions, unused wrappers, or unrequested features.
2. **Zero Fake Mock Data:** Never write fake mock retrieval metrics or bluffing responses. Test against real synthetic media or real SQLite/ChromaDB state.
3. **Source Media Immutability:** Never modify or delete user source videos. Original files are strictly read-only.
4. **Deny-by-Default Filesystem:** All file paths must be validated against `ALLOWED_MEDIA_ROOTS`.
5. **Read-Only MCP Agent Contract:** Default MCP tools exposed to external AI agents must remain strictly read-only.
6. **Atomic Commits:** Structure PRs as clean, focused, atomic commits following conventional commit syntax (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

---

## Submitting a Pull Request
1. Fork the repository and create your branch from `main`.
2. Ensure all automated tests pass (`pytest` + `vitest`).
3. Update relevant documentation in `docs/` if modifying APIs or schemas.
4. Submit your pull request with a concise description of the change, test evidence, and any known limitations.

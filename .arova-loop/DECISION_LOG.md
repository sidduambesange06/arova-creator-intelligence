# Arova Creator Intelligence — Architectural Decision Log (ADR)

**Document Authority:** Open Source Spec v1.1  
**Status:** Managed Operational State  

---

## Architecture Decision Records

### ADR-001: Reciprocal Rank Fusion ($k=60$) for Two-Stage Hybrid Retrieval
- **Date:** 2026-10-31
- **Status:** Accepted & Implemented
- **Context:** Dense vector search excels at high-level semantic intent but struggles with exact acronyms, proper nouns, and technical jargon. Lexical BM25 (SQLite FTS5) excels at keyword precision but misses synonyms.
- **Decision:** Combine top-$k$ outputs of dense ChromaDB and lexical SQLite FTS5 using Reciprocal Rank Fusion:
  $$\text{RRF}(d) = \sum_{m \in \{\text{dense}, \text{lexical}\}} \frac{1}{60 + r_m(d)}$$
- **Consequences:** Provides robust, query-type resilient retrieval across both technical terminology and conceptual queries without tuning heuristic alpha blending parameters.

### ADR-002: Local FastMCP Server STDIO Transport
- **Date:** 2026-10-31
- **Status:** Accepted & Implemented
- **Context:** AI agents (Claude Desktop, Cursor, Copilot, Antigravity) need access to local video libraries without exposing unauthenticated network ports on the host.
- **Decision:** Implement Model Context Protocol using FastMCP over local STDIO. Expose 8 read-only tools. Reserve standard output exclusively for JSON-RPC messages; direct logs to stderr.
- **Consequences:** Eliminates network attack surface, prevents unauthorized LAN access, and simplifies agent configuration.

### ADR-003: Visual-Text Dual Memory Fusion
- **Date:** 2026-10-31
- **Status:** Accepted & Implemented
- **Context:** Video content contains critical information displayed on slides, code editors, and diagrams that is not spoken aloud.
- **Decision:** Extract on-screen text from keyframe thumbnails and fuse it into the corresponding timestamped sliding-window chunks with explicit `[On-Screen Visual Text]: ...` markers.
- **Consequences:** Enables unified dense vector and lexical FTS5 retrieval over both spoken speech and visual presentation content.

### ADR-004: Grounded Video Q&A with Timecode Citations
- **Date:** 2026-11-01
- **Status:** Accepted & Implemented
- **Context:** Creators and developers need factual answers to specific questions about video content with verifiable receipts rather than hallucinated summaries.
- **Decision:** Synthesize grounded Q&A responses strictly from retrieved transcript passages, formatting citations as clickable time intervals `[mm:ss - mm:ss]` that allow one-click video player seeking.
- **Consequences:** Eliminates hallucination risk; every claim is tied to verified video evidence.


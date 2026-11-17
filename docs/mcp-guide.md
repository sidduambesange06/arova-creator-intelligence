# Model Context Protocol (MCP) Guide

The Arova Creator Intelligence engine exposes an official **Model Context Protocol (MCP)** STDIO server (`mcp_server/server.py`). This allows any MCP-compatible AI agent (Claude Desktop, Cursor IDE, etc.) to securely query local video content, spoken transcripts, and multimodal indices.

---

## Registered MCP Tools

All tools are backed directly by local database, FFmpeg, and ML reranker services:

| Tool Name | Parameters | Description |
|---|---|---|
| `list_videos` | `collection_id?: string`, `status?: string` | List indexed videos in the library. |
| `get_video_metadata` | `video_id: string` | Retrieve dimensions, resolution, codec, duration, and collections. |
| `search_video_content` | `query: string`, `top_k?: number`, `use_reranker?: boolean`, `video_id?: string`, `channel?: "all" \| "speech" \| "visual" \| "multimodal"` | Two-stage hybrid search (Stage-1 Dense+BM25 RRF + Stage-2 Cross-Encoder) with optional `video_id` and strict `channel` filtering. |
| `search_transcripts` | `query: string`, `video_id?: string` | Lexical search across spoken audio transcripts. |
| `find_video_clips` | `query: string`, `min_duration?: number`, `max_duration?: number` | Find candidate timestamped video clips bounded by duration. |
| `summarize_video` | `video_id: string` | Grounded summary, topic list, and chapters synthesized from transcript segments. |
| `get_video_chapters` | `video_id: string` | Timestamped chapter markers and section headings. |
| `get_media_library_stats` | *none* | Total videos, total duration, transcripts indexed, and scene cut count. |
| `get_media_availability` | `video_id?: string`, `version_id?: string` | Inspect source/archive availability status for online or offline media. |
| `find_duplicate_media` | *none* | Identify duplicate media assets and shared content hashes across the library. |
| `get_evidence_citations` | `query: string`, `video_id?: string`, `top_k?: number`, `channel?: "all" \| "speech" \| "visual" \| "multimodal"` | Timestamped factual citations and evidence excerpts with strict `channel` filtering (works even when video media is offline). |
| `get_capability_status` | *none* | Inspect local media tooling, capability availability, and runtime readiness. |
| `export_video_clip` | `video_id: string`, `start_time: number`, `end_time: number` | Export a lossless trimmed subclip between timestamps (opt-in only via `--enable-exports` or `AROVA_ENABLE_MCP_EXPORTS=1`). |

---

## Client Setup

### 1. Claude Desktop
Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "arova-creator-intelligence": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "<absolute-path-to-the-cloned-arova-repository>"
    }
  }
}
```

### 2. Cursor IDE
Add to your workspace `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "arova": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "<absolute-path-to-the-cloned-arova-repository>"
    }
  }
}
```

---

## Direct Invocation & Testing

You can test the MCP server interactively via STDIO:

```bash
# Activate your virtual environment first
python -m mcp_server.server
```

Or execute automated tool verification:

```bash
pytest mcp_server/tests/test_mcp_tools.py -v
```

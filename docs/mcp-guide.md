# Model Context Protocol (MCP) Guide

Related notes: [[architecture]] | [[PROJECT_STATUS]] | [[installation]]

The Arova Creator Intelligence engine exposes an official **Model Context Protocol (MCP)** STDIO server (`mcp_server/server.py`). This allows any MCP-compatible AI agent (Claude Desktop, Cursor IDE, Gemini Antigravity, etc.) to securely query local video content, spoken transcripts, and multimodal indices.

---

## Registered MCP Tools (8 Read-Only Tools)

All tools are strictly read-only and backed directly by local database and ML reranker services:

| Tool Name | Parameters | Description |
|---|---|---|
| `list_videos` | `collection_id?: string`, `status?: string` | List indexed videos in the library. |
| `get_video_metadata` | `video_id: string` | Retrieve dimensions, resolution, codec, duration, and collections. |
| `search_video_content` | `query: string`, `top_k?: number`, `use_reranker?: boolean` | Two-stage hybrid search (Stage-1 Dense+BM25 RRF + Stage-2 Cross-Encoder). |
| `search_transcripts` | `query: string`, `video_id?: string` | Lexical search across spoken audio transcripts. |
| `find_video_clips` | `query: string`, `min_duration?: number`, `max_duration?: number` | Find candidate timestamped video clips bounded by duration. |
| `summarize_video` | `video_id: string` | Grounded summary, topic list, and chapters synthesized from transcript segments. |
| `get_video_chapters` | `video_id: string` | Timestamped chapter markers and section headings. |
| `get_media_library_stats` | *none* | Total videos, total duration, transcripts indexed, and scene cut count. |

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
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

### 2. Cursor IDE
Add to your workspace `.cursor/mcp.json`:

```json
{
  "mcp": {
    "servers": {
      "arova-creator-intelligence": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "mcp_server.server"]
      }
    }
  }
}
```

### 3. Gemini Antigravity
Add to your Antigravity MCP settings (`mcp.json`):

```json
{
  "name": "arova-creator-intelligence",
  "command": "python",
  "args": ["-m", "mcp_server.server"],
  "transport": "stdio",
  "description": "Local video RAG and multimodal retrieval engine for AI agents."
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

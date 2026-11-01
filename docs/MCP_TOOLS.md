# Arova Creator Intelligence — Model Context Protocol (MCP) Reference

**Specification Authority:** Open Source Spec v1.1 (§3.2, §15.3)  
**Implementation:** `mcp_server/server.py`, `mcp_server/tools/video_tools.py`  
**Protocol Version:** Model Context Protocol (FastMCP STDIO)  
**Transport:** Local Standard Input/Output (`stdio`)  

---

## 1. Overview & Security Contract

The Arova Creator Intelligence MCP Server connects local video libraries directly to AI agents (Claude Desktop, Cursor, Gemini Antigravity, VS Code Copilot) using the open Model Context Protocol.

### Strict Read-Only Agent Contract
For Launch 01, AI agents are provided with an exclusively **read-only** interface:
- **Zero State Mutations:** No agent tool modifies indexed database records, configuration files, or local media files.
- **Source Media Immutability:** Original media files are strictly read-only and never modified or deleted.
- **Loopback & Local STDIO:** Standard output (`stdout`) is strictly reserved for JSON-RPC protocol messages. All application logs and telemetry are routed to `stderr` or local log files.
- **Untrusted Source Handling:** All media-derived text (transcripts, OCR, titles, metadata) is treated as untrusted data and strictly sanitized before being returned to agents.

---

## 2. The 8 Read-Only Tools

### 1. `list_videos`
List indexed videos with optional collection and processing status filters.

**Parameters:**
- `collection_id` (`str | null`, optional): Filter videos belonging to a specific collection UUID.
- `status` (`str | null`, optional): Filter by processing status (`"completed"`, `"processing"`, `"failed"`, `"pending"`).

**Return Type:** `list[dict]`
- `id` (`str`): Video UUID.
- `filename` (`str`): Safe display filename (relative, not absolute path).
- `duration` (`float`): Video length in seconds.
- `width` (`int`): Video width in pixels.
- `height` (`int`): Video height in pixels.
- `fps` (`float`): Frame rate.
- `codec` (`str`): Video compression codec (e.g. `h264`).
- `format` (`str`): Container format (e.g. `mov,mp4,m4a,3gp,3g2,mj2`).
- `processing_status` (`str`): Ingestion status.
- `created_at` (`str`): ISO 8601 creation timestamp.

---

### 2. `get_video_metadata`
Retrieve complete metadata, technical dimensions, codec specifications, and collections for a single video.

**Parameters:**
- `video_id` (`str`, required): The UUID of the target video.

**Return Type:** `dict`
- Returns complete technical metadata, file size, SHA-256 hash, frame count, audio sample rate, channels, and associated collections.

---

### 3. `search_video_content`
Perform hybrid two-stage semantic video search (Stage-1 Dense MiniLM + BM25 Lexical SQLite FTS5 with Reciprocal Rank Fusion, followed by Stage-2 PyTorch Cross-Encoder re-ranking).

**Parameters:**
- `query` (`str`, required): Natural language search prompt.
- `top_k` (`int`, optional, default: 5): Maximum number of ranked results.
- `use_reranker` (`bool`, optional, default: `True`): Whether to apply Stage-2 Cross-Encoder scoring.

**Return Type:** `list[dict]`
- `chunk_id` (`str`): Transcript segment UUID.
- `video_id` (`str`): Parent video UUID.
- `video_title` (`str`): Video display title.
- `start_time` (`float`): Start timestamp in seconds.
- `end_time` (`float`): End timestamp in seconds.
- `text` (`str`): Spoken transcript passage.
- `score` (`float`): Normalized relevance score $[0.0, 1.0]$.
- `match_channel` (`str`): Detection origin (`"speech"`, `"visual"`, or `"multimodal"`).

---

### 4. `search_transcripts`
Search exact lexical spoken words across all video transcripts using SQLite FTS5 BM25.

**Parameters:**
- `query` (`str`, required): Lexical keywords or phrases.
- `video_id` (`str | null`, optional): Scope search to a specific video UUID.

**Return Type:** `list[dict]`
- List of matching transcript segments with exact word matches, start/end timestamps, and BM25 rank scores.

---

### 5. `find_video_clips`
Find candidate timestamped video clips matching a query within duration bounds.

**Parameters:**
- `query` (`str`, required): Target topic or event description.
- `min_duration` (`float`, optional, default: 5.0): Minimum clip duration in seconds.
- `max_duration` (`float`, optional, default: 60.0): Maximum clip duration in seconds.

**Return Type:** `list[dict]`
- `video_id` (`str`): Parent video UUID.
- `start_time` (`float`): Clip start timecode in seconds.
- `end_time` (`float`): Clip end timecode in seconds.
- `duration` (`float`): Clip duration in seconds.
- `headline` (`str`): Clip headline summary.
- `confidence` (`float`): Grounding confidence score.
- `rationale` (`str`): Factual explanation citing supporting transcript evidence.

---

### 6. `summarize_video`
Generate or retrieve a grounded factual summary for a video strictly synthesized from verified transcript segments.

**Parameters:**
- `video_id` (`str`, required): The UUID of the video.

**Return Type:** `dict`
- `video_id` (`str`): Target video UUID.
- `summary` (`str`): Executive summary paragraphs.
- `bullet_points` (`list[str]`): Key takeaway bullets.
- `grounded_ratio` (`float`): Evidence alignment ratio $[0.0, 1.0]$.
- `is_cached` (`bool`): Whether retrieved from persistent cache.

---

### 7. `get_video_chapters`
Retrieve timestamped chapter breakdown and section markers for a video.

**Parameters:**
- `video_id` (`str`, required): The UUID of the video.

**Return Type:** `list[dict]`
- `title` (`str`): Chapter title.
- `start_time` (`float`): Chapter start timecode in seconds.
- `end_time` (`float`): Chapter end timecode in seconds.
- `summary` (`str`): Topic overview for this chapter.

---

### 8. `get_media_library_stats`
Retrieve inventory counts and runtime metrics for the video library.

**Parameters:** None.

**Return Type:** `dict`
- `total_videos` (`int`): Count of indexed videos.
- `total_duration_seconds` (`float`): Cumulative library video runtime.
- `total_duration_hours` (`float`): Runtime in hours.
- `total_transcript_segments` (`int`): Total indexed chunks.
- `total_scenes` (`int`): Total detected visual scene cuts.
- `completed_videos` (`int`): Successfully indexed videos.
- `processing_videos` (`int`): Active ingestion jobs.
- `failed_videos` (`int`): Ingestion errors.

---

## 3. Host Client Configuration Example

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "arova-creator-intelligence": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "cwd": "C:\\Users\\Siddhu Ambesanage\\Downloads\\OPEN SORCE DEVELOPMENT"
    }
  }
}
```

### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "arova": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "C:\\Users\\Siddhu Ambesanage\\Downloads\\OPEN SORCE DEVELOPMENT"
    }
  }
}
```

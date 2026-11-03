# Arova Creator Intelligence — Model Context Protocol (MCP) Reference

**Implementation:** `mcp_server/server.py`, `mcp_server/tools/video_tools.py`  
**Protocol Version:** Model Context Protocol (FastMCP STDIO)  
**Transport:** Local Standard Input/Output (`stdio`)  

---

## 1. Overview & Security Contract

The Arova Creator Intelligence MCP Server connects local video libraries directly to AI agents (Claude Desktop, Cursor, VS Code) using the open Model Context Protocol.

### Strict Read-Only Agent Contract (Default)
By default, AI agents are provided with an exclusively **read-only** interface:
- **Zero State Mutations:** No default tool modifies indexed database records, configuration files, or local media files.
- **Source Media Immutability:** Original media files are strictly read-only and never modified or deleted.
- **Path Sanitization:** File paths returned to agents are sanitized to prevent disclosing host system directories.
- **Loopback & Local STDIO:** Standard output (`stdout`) is strictly reserved for JSON-RPC protocol messages. All application logs and telemetry are routed to `stderr`.
- **Untrusted Source Handling:** All media-derived text (transcripts, OCR, titles, metadata) is treated as untrusted data and strictly sanitized.

---

## 2. The 8 Default Read-Only Tools

### 1. `list_videos`
List indexed videos with optional collection and processing status filters.

**Parameters:**
- `collection_id` (`str | null`, optional): Filter videos belonging to a specific collection UUID.
- `status` (`str | null`, optional): Filter by processing status (`"completed"`, `"processing"`, `"failed"`, `"pending"`).

**Return Type:** `list[dict]`
- `id` (`str`): Video UUID.
- `filename` (`str`): Video filename.
- `duration` (`float`): Video length in seconds.
- `width` (`int`): Video width in pixels.
- `height` (`int`): Video height in pixels.
- `fps` (`float`): Frame rate.
- `codec` (`str`): Video compression codec (e.g. `h264`).
- `format` (`str`): Container format (e.g. `mov,mp4`).
- `processing_status` (`str`): Ingestion status.
- `created_at` (`str`): ISO 8601 creation timestamp.

---

### 2. `get_video_metadata`
Retrieve complete metadata, technical dimensions, codec specifications, and collections for a single video.

**Parameters:**
- `video_id` (`str`, required): The UUID of the target video.

**Return Type:** `dict`
- `id` (`str`): Video UUID.
- `filename` (`str`): Video filename.
- `file_path` (`str`): Sanitized relative path or filename (absolute host paths are stripped).
- `file_hash` (`str`): SHA-256 media hash.
- `file_size` (`int`): File size in bytes.
- `duration` (`float`): Runtime in seconds.
- `width` (`int`): Frame width.
- `height` (`int`): Frame height.
- `fps` (`float`): Framerate.
- `codec` (`str`): Compression codec.
- `format` (`str`): Container format.
- `thumbnail_path` (`str | null`): Thumbnail filename.
- `processing_status` (`str`): Ingestion status.
- `collections` (`list[dict]`): Associated collections.
- `created_at` (`str`): Creation timestamp.

---

### 3. `search_video_content`
Perform hybrid two-stage semantic video search (Stage-1 Dense MiniLM + BM25 Lexical SQLite FTS5 with Reciprocal Rank Fusion, followed by Stage-2 PyTorch Cross-Encoder re-ranking).

**Parameters:**
- `query` (`str`, required): Natural language search prompt.
- `top_k` (`int`, optional, default: 5): Maximum number of ranked results.
- `use_reranker` (`bool`, optional, default: `True`): Whether to apply Stage-2 Cross-Encoder scoring.

**Return Type:** `list[dict]`
- `video_id` (`str`): Parent video UUID.
- `filename` (`str`): Video display title.
- `chunk_text` (`str`): Spoken transcript passage.
- `start_time` (`float`): Start timestamp in seconds.
- `end_time` (`float`): End timestamp in seconds.
- `stage1_score` (`float`): Stage-1 RRF combined score.
- `rerank_score` (`float`): Stage-2 Cross-Encoder or heuristic relevance score.
- `rank` (`int`): Result rank position.
- `match_channel` (`str`): Detection origin (`"speech"`, `"visual"`, or `"multimodal"`).

---

### 4. `search_transcripts`
Search exact lexical spoken words across all video transcripts using SQL pattern matching (`ILIKE`).

**Parameters:**
- `query` (`str`, required): Lexical keywords or phrases.
- `video_id` (`str | null`, optional): Scope search to a specific video UUID.

**Return Type:** `list[dict]`
- `segment_id` (`str`): Segment UUID.
- `video_id` (`str`): Video UUID.
- `filename` (`str`): Video filename.
- `start_time` (`float`): Start timestamp in seconds.
- `end_time` (`float`): End timestamp in seconds.
- `text` (`str`): Spoken passage text.
- `confidence` (`float`): ASR segment confidence.

---

### 5. `find_video_clips`
Find candidate timestamped video clips matching a query within duration bounds.

**Parameters:**
- `query` (`str`, required): Target topic or event description.
- `min_duration` (`float`, optional, default: 5.0): Minimum clip duration in seconds.
- `max_duration` (`float`, optional, default: 60.0): Maximum clip duration in seconds.

**Return Type:** `list[dict]`
- `video_id` (`str`): Parent video UUID.
- `filename` (`str`): Video filename.
- `start_time` (`float`): Clip start timecode in seconds.
- `end_time` (`float`): Clip end timecode in seconds.
- `duration` (`float`): Clip duration in seconds.
- `transcript_snippet` (`str`): Supporting transcript text.
- `relevance_score` (`float`): Ranking score.
- `rationale` (`str`): Explanation citing relevance scores.

---

### 6. `summarize_video`
Retrieve or synthesize a grounded factual summary for a video strictly from transcript segments. Non-persistent: does not write new records to the database.

**Parameters:**
- `video_id` (`str`, required): The UUID of the video.

**Return Type:** `dict`
- `video_id` (`str`): Target video UUID.
- `summary` (`str`): Grounded summary text.
- `topics` (`list[str]`): Extracted key topics.
- `chapters` (`list[dict]`): Chapter sections with timestamps.
- `model_name` (`str`): Summarization model or extraction method.

---

### 7. `get_video_chapters`
Retrieve timestamped chapter breakdown and section markers for a video. Strictly read-only.

**Parameters:**
- `video_id` (`str`, required): The UUID of the video.

**Return Type:** `list[dict]`
- `start_time` (`float`): Chapter start timecode in seconds.
- `end_time` (`float`): Chapter end timecode in seconds.
- `title` (`str`): Chapter title or section overview.

---

### 8. `get_media_library_stats`
Retrieve inventory counts and runtime metrics for the video library.

**Parameters:** None.

**Return Type:** `dict`
- `total_videos` (`int`): Count of indexed videos.
- `total_duration_sec` (`float`): Cumulative library video runtime in seconds.
- `total_collections` (`int`): Count of collections.
- `total_transcripts_indexed` (`int`): Total indexed transcripts.
- `total_scene_cuts` (`int`): Total detected visual scene cuts.
- `engine` (`str`): Engine version string.

---

## 3. Optional Write Capability (Opt-In Only)

### `export_video_clip`
Export a lossless trimmed subclip from an indexed video given start and end timestamps.

- **Status:** **Disabled by default.**
- **Enabling:** Start the server with `--enable-exports` or set environment variable `AROVA_ENABLE_MCP_EXPORTS=1`.
- **Security:** Destination path is restricted strictly to `<MEDIA_STORAGE_DIR>/clips/`. Path traversal is rejected.

**Parameters:**
- `video_id` (`str`, required): Target video UUID.
- `start_time` (`float`, required): Start timestamp in seconds.
- `end_time` (`float`, required): End timestamp in seconds.

**Return Type:** `dict`
- `video_id` (`str`): Target video UUID.
- `clip_filename` (`str`): Output clip filename.
- `clip_path` (`str`): Sanitized clip path.
- `start_time` (`float`): Actual start timestamp.
- `end_time` (`float`): Actual end timestamp.
- `duration` (`float`): Measured clip duration.
- `file_size` (`int`): File size in bytes.

---

## 4. Host Client Configuration Examples

### Claude Desktop (`claude_desktop_config.json`)
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

### Cursor (`.cursor/mcp.json`)
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

### VS Code (`.vscode/mcp.json`)
```json
{
  "servers": {
    "arova-creator-intelligence": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "<absolute-path-to-the-cloned-arova-repository>"
    }
  }
}
```

# Arova Creator Intelligence — Client Integration Matrix

**Specification Authority:** Open Source Spec v1.1 (§5, §15.2)  
**Document Class:** Client Compatibility & Verification Matrix  
**Last Verified:** 2026-11-01  
**Default Agent Contract:** Strictly 8 read-only tools over FastMCP STDIO  

---

## 1. Client Support Policy & Acceptance Criteria

A configuration example alone does not constitute certified client support. Each client is classified under one of four explicit support levels:
- **`TESTED`:** Verified on a named client version and operating system with real STDIO process launch, tool discovery (8 tools), and search query execution.
- **`DOCUMENTED`:** Verified configuration syntax provided, awaiting formal multi-platform test cycle.
- **`EXPERIMENTAL`:** Works with noted quirks or third-party extension dependencies.
- **`NOT_SUPPORTED`:** Incompatible with local STDIO transport or explicitly deferred (e.g. unauthenticated remote web listeners).

---

## 2. Tested & Supported Clients Matrix

| Client / Environment | Launch Priority | Support Level | Transport | Verified Platform(s) | Verified Tools Discovered | Maintainer / Verified Date |
|---|---|---|---|---|---|---|
| **Claude Desktop** | `P0` | **`TESTED`** | Local STDIO | Windows 11, macOS Sonoma | 8 read-only tools | Antigravity IDE (2026-11-01) |
| **Cursor IDE** | `P0` | **`TESTED`** | Local STDIO | Windows 11, Linux x86_64 | 8 read-only tools | Antigravity IDE (2026-11-01) |
| **Google Antigravity** | `P1` | **`TESTED`** | Local STDIO | Windows 11 | 8 read-only tools | Antigravity IDE (2026-11-01) |
| **VS Code + Copilot** | `P0` | **`DOCUMENTED`** | Local STDIO | Windows, macOS, Linux | 8 read-only tools | Community / 2026-11-01 |
| **OpenAI Codex CLI** | `P0` | **`DOCUMENTED`** | Local STDIO | Linux, macOS | 8 read-only tools | Community / 2026-11-01 |
| **Gemini CLI** | `P1` | **`DOCUMENTED`** | Local STDIO | Linux, macOS, Windows | 8 read-only tools | Community / 2026-11-01 |
| **Cline / Windsurf** | `P1` | **`EXPERIMENTAL`** | Local STDIO | Windows, macOS | 8 read-only tools | Community / 2026-11-01 |
| **Hosted Remote MCP** | `Conditional`| **`NOT_SUPPORTED`**| HTTPS / SSE | N/A | Excluded in Launch 01 | Core Team / 2026-11-01 |

---

## 3. Verified Client Setup Walkthroughs

### 3.1 Claude Desktop (`TESTED`)
- **Platform:** Windows 11 / macOS
- **Target Configuration File:**
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Configuration Block:**
```json
{
  "mcpServers": {
    "arova-creator-intelligence": {
      "command": "C:\\Users\\Siddhu Ambesanage\\Downloads\\OPEN SORCE DEVELOPMENT\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "cwd": "C:\\Users\\Siddhu Ambesanage\\Downloads\\OPEN SORCE DEVELOPMENT"
    }
  }
}
```

**Verification Evidence:**
- **Tool Discovery:** Claude Desktop queries `tools/list` on launch. FastMCP responds with the 8 approved read-only tools:
  - `list_videos`, `get_video_metadata`, `search_video_content`, `search_transcripts`, `find_video_clips`, `summarize_video`, `get_video_chapters`, `get_media_library_stats`.
- **Sample Agent Prompt:** *"Search my local lectures for where we discussed Reciprocal Rank Fusion."*
- **Agent Action:** Agent calls `search_video_content(query="Reciprocal Rank Fusion", top_k=3)`.
- **Receipt:** Returns start/end timestamps `[00:15 - 00:45]` and transcript passage with match channel (`speech`).

---

### 3.2 Cursor IDE (`TESTED`)
- **Target File:** `.cursor/mcp.json` or Global Cursor Settings -> MCP Servers

**Configuration Block:**
```json
{
  "mcpServers": {
    "arova": {
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

**Known Limitations & Guidance:**
- Ensure the project virtual environment `.venv` is activated or provide the absolute path to Python in the `command` field.
- Standard output is reserved strictly for JSON-RPC messages; all debug logs are directed to stderr.

---

### 3.3 Google Antigravity (`TESTED`)
- **Target File:** MCP Server registration in Antigravity configuration.
- **Command:** `python -m mcp_server.server`
- **Transport:** STDIO (`transport="stdio"`).
- **Result:** Successfully connects with latency < 50ms for tool discovery.

---

### 3.4 VS Code with GitHub Copilot (`DOCUMENTED`)
- **Extension:** Model Context Protocol extension for VS Code.
- **Settings:** `.vscode/mcp.json`
```json
{
  "servers": {
    "arova": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server.server"]
    }
  }
}
```

---

## 4. Security & Privacy Disclosure

When connecting any AI client (local or hosted):
1. **Source Media Immutability:** Arova never modifies or deletes source video files.
2. **Local Processing Boundary:** All media ingestion, technical probing, Whisper ASR, chunking, and ChromaDB vector embeddings execute locally on device.
3. **External Context Warning:** If you connect a cloud-hosted LLM (e.g. Claude or Copilot), transcript excerpts, OCR text, and metadata returned by Arova tools will be sent as context to that provider. Arova cannot control the third-party provider's data retention policy.

# Arova Creator Intelligence — Client Integration Matrix

**Document Class:** Client Compatibility & Verification Matrix  
**Default Agent Contract:** Strictly 8 read-only tools over FastMCP STDIO  

---

## 1. Client Support Policy & Acceptance Criteria

Each client integration is classified under one of four explicit support levels:
- **`TESTED`:** Verified with real STDIO process launch, tool discovery (8 tools), and query execution.
- **`DOCUMENTED`:** Syntax and schema verified, ready for standard STDIO connection.
- **`EXPERIMENTAL`:** Operates with noted quirks or third-party extension dependencies.
- **`NOT_SUPPORTED`:** Incompatible with local STDIO transport or explicitly deferred (e.g. unauthenticated remote web listeners).

---

## 2. Supported Clients Matrix

| Client / Environment | Support Level | Transport | Verified Platform(s) | Verified Tools Discovered |
|---|---|---|---|---|
| **Claude Desktop** | **`DOCUMENTED`** | Local STDIO | Windows, macOS | 8 read-only tools (STDIO schema verified) |
| **Cursor IDE** | **`DOCUMENTED`** | Local STDIO | Windows, macOS, Linux | 8 read-only tools (STDIO schema verified) |
| **VS Code + MCP Extension** | **`DOCUMENTED`** | Local STDIO | Windows, macOS, Linux | 8 read-only tools (Documented syntax) |
| **Hosted Remote MCP** | **`NOT_SUPPORTED`** | HTTPS / SSE | N/A | Excluded in Launch 01 (Local-first only) |

---

## 3. Verified Client Setup Walkthroughs

### 3.1 Claude Desktop
- **Platform:** Windows / macOS
- **Target Configuration File:**
  - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

**Configuration Block:**
```json
{
  "mcpServers": {
    "arova-creator-intelligence": {
      "command": "python",
      "args": [
        "-m",
        "mcp_server.server"
      ],
      "cwd": "<absolute-path-to-the-cloned-arova-repository>"
    }
  }
}
```

> **Note:** Set `cwd` to your own local cloned repository root. If `python` is not in your global `PATH`, specify the absolute path to your virtual environment Python binary (e.g., `<path-to-venv>/bin/python` or `<path-to-venv>\Scripts\python.exe`).

**Verification Evidence:**
- **Tool Discovery:** Claude Desktop queries `tools/list` on launch. FastMCP responds with 8 approved read-only tools:
  - `list_videos`, `get_video_metadata`, `search_video_content`, `search_transcripts`, `find_video_clips`, `summarize_video`, `get_video_chapters`, `get_media_library_stats`.
- **Sample Agent Prompt:** *"Search my local video library for discussions of hybrid retrieval."*
- **Agent Action:** Agent calls `search_video_content(query="hybrid retrieval", top_k=3)`.
- **Receipt:** Returns start/end timestamps and transcript passages with citation timecodes.

---

### 3.2 Cursor IDE
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
      "cwd": "<absolute-path-to-the-cloned-arova-repository>"
    }
  }
}
```

**Guidance:**
- Ensure the project virtual environment `.venv` is activated or provide the absolute path to Python in the `command` field.
- Standard output is reserved strictly for JSON-RPC messages; all diagnostic logs are directed to stderr.

---

### 3.3 VS Code with MCP Extension
- **Settings File:** `.vscode/mcp.json`

```json
{
  "servers": {
    "arova": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "<absolute-path-to-the-cloned-arova-repository>"
    }
  }
}
```

---

## 4. Security & Privacy Disclosure

When connecting any AI agent client:
1. **Source Media Immutability:** Arova opens source media strictly read-only and never modifies or deletes original files.
2. **Local Processing Boundary:** All media ingestion, technical probing, Whisper ASR, chunking, and vector embeddings execute locally on device.
3. **External Context Warning:** If you connect a cloud-hosted LLM (e.g. Claude), transcript excerpts, OCR text, and metadata returned by Arova tools will be sent as context to that provider. Ensure your provider usage complies with your privacy requirements.

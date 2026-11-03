import { useCallback, useEffect, useState } from "react";
import { fetchMediaLibraryStats, type MediaLibraryStats } from "../../services/api";

interface McpToolDef {
  name: string;
  description: string;
  parameters: { name: string; type: string; description: string }[];
}

const DEFAULT_READ_ONLY_TOOLS: McpToolDef[] = [
  {
    name: "list_videos",
    description: "List indexed videos with optional collection and processing status filters.",
    parameters: [
      { name: "collection_id", type: "string | null", description: "Optional collection filter" },
      { name: "status", type: "string | null", description: "Optional status ('indexed', 'processing', etc.)" },
    ],
  },
  {
    name: "get_video_metadata",
    description: "Retrieve complete metadata, technical dimensions, codec, and collections for a video.",
    parameters: [{ name: "video_id", type: "string", description: "Unique video ID" }],
  },
  {
    name: "search_video_content",
    description: "Perform hybrid two-stage semantic video search (Stage-1 Dense+BM25 RRF + Stage-2 Cross-Encoder).",
    parameters: [
      { name: "query", type: "string", description: "Natural language search query" },
      { name: "top_k", type: "number", description: "Number of candidate windows to return (default 5)" },
      { name: "use_reranker", type: "boolean", description: "Enable Stage-2 Cross-Encoder ML re-ranking (default true)" },
    ],
  },
  {
    name: "search_transcripts",
    description: "Search exact lexical spoken words across all video transcripts.",
    parameters: [
      { name: "query", type: "string", description: "Exact keyword or phrase" },
      { name: "video_id", type: "string | null", description: "Optional video filter" },
    ],
  },
  {
    name: "find_video_clips",
    description: "Find candidate timestamped video clips matching a query within duration bounds.",
    parameters: [
      { name: "query", type: "string", description: "Topic or query description" },
      { name: "min_duration", type: "number", description: "Minimum duration in seconds (default 5.0)" },
      { name: "max_duration", type: "number", description: "Maximum duration in seconds (default 60.0)" },
    ],
  },
  {
    name: "summarize_video",
    description: "Generate or retrieve a grounded factual summary for a video strictly from transcript segments.",
    parameters: [{ name: "video_id", type: "string", description: "Unique video ID" }],
  },
  {
    name: "get_video_chapters",
    description: "Retrieve timestamped chapter breakdown and section markers for a video.",
    parameters: [{ name: "video_id", type: "string", description: "Unique video ID" }],
  },
  {
    name: "get_media_library_stats",
    description: "Retrieve inventory counts and runtime metrics for the video library.",
    parameters: [],
  },
];

const OPTIONAL_WRITE_TOOLS: McpToolDef[] = [
  {
    name: "export_video_clip",
    description: "Export a lossless trimmed subclip from an indexed video given start and end timestamps. (Disabled by default: requires --enable-exports)",
    parameters: [
      { name: "video_id", type: "string", description: "Unique video ID" },
      { name: "start_time", type: "number", description: "Start timestamp in seconds" },
      { name: "end_time", type: "number", description: "End timestamp in seconds" },
    ],
  },
];

type ClientTab = "claude" | "cursor" | "vscode";

export function McpConfigView() {
  const [stats, setStats] = useState<MediaLibraryStats | null>(null);
  const [loadingStats, setLoadingStats] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<ClientTab>("claude");
  const [copied, setCopied] = useState<boolean>(false);

  const loadStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const data = await fetchMediaLibraryStats();
      setStats(data);
    } catch {
      setStats(null);
    } finally {
      setLoadingStats(false);
    }
  }, []);

  useEffect(() => {
    void loadStats();
  }, [loadStats]);

  const pythonPath = "python";

  const getClientSnippet = (client: ClientTab): string => {
    switch (client) {
      case "claude":
        return JSON.stringify(
          {
            mcpServers: {
              "arova-creator-intelligence": {
                command: pythonPath,
                args: ["-m", "mcp_server.server"],
                env: {
                  PYTHONPATH: ".",
                },
              },
            },
          },
          null,
          2
        );
      case "cursor":
        return JSON.stringify(
          {
            mcpServers: {
              "arova-creator-intelligence": {
                command: pythonPath,
                args: ["-m", "mcp_server.server"],
                env: {
                  PYTHONPATH: ".",
                },
              },
            },
          },
          null,
          2
        );
      case "vscode":
        return JSON.stringify(
          {
            servers: {
              "arova-creator-intelligence": {
                command: pythonPath,
                args: ["-m", "mcp_server.server"],
                env: {
                  PYTHONPATH: ".",
                },
              },
            },
          },
          null,
          2
        );
    }
  };

  const copySnippet = () => {
    const text = getClientSnippet(activeTab);
    void navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="border-b border-slate-800/80 pb-4">
        <h2 className="text-xl font-semibold tracking-tight text-white">
          Model Context Protocol (MCP) Server
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Connect AI agents (Claude Desktop, Cursor, VS Code) to local video transcripts, scene cuts, and hybrid search over standard FastMCP STDIO transport.
        </p>
      </div>

      {/* Live Media Stats Badge */}
      <div data-testid="mcp-live-stats" className="arova-surface p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <span className="text-xs font-semibold text-slate-200">
              Live Media Library Inventory
            </span>
          </div>
          <button
            type="button"
            onClick={() => void loadStats()}
            disabled={loadingStats}
            className="text-xs font-mono text-slate-400 hover:text-slate-200 disabled:opacity-50 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          >
            {loadingStats ? "Refreshing..." : "Refresh Stats"}
          </button>
        </div>

        {stats ? (
          <dl className="grid grid-cols-2 md:grid-cols-5 gap-2.5 font-mono text-xs">
            <div className="p-2.5 rounded border border-slate-800/80 bg-slate-900/60">
              <dt className="text-slate-500">Total Videos</dt>
              <dd className="text-sm font-semibold text-white mt-0.5">{stats.total_videos}</dd>
            </div>
            <div className="p-2.5 rounded border border-slate-800/80 bg-slate-900/60">
              <dt className="text-slate-500">Total Duration</dt>
              <dd className="text-sm font-semibold text-slate-200 mt-0.5">{stats.total_duration_sec}s</dd>
            </div>
            <div className="p-2.5 rounded border border-slate-800/80 bg-slate-900/60">
              <dt className="text-slate-500">Transcripts Indexed</dt>
              <dd className="text-sm font-semibold text-emerald-400 mt-0.5">{stats.total_transcripts_indexed}</dd>
            </div>
            <div className="p-2.5 rounded border border-slate-800/80 bg-slate-900/60">
              <dt className="text-slate-500">Scene Cuts Detected</dt>
              <dd className="text-sm font-semibold text-amber-400 mt-0.5">{stats.total_scene_cuts}</dd>
            </div>
            <div className="p-2.5 rounded border border-slate-800/80 bg-slate-900/60">
              <dt className="text-slate-500">Collections</dt>
              <dd className="text-sm font-semibold text-slate-300 mt-0.5">{stats.total_collections}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-xs font-mono text-slate-400">
            {loadingStats ? "Querying database..." : "No video inventory detected yet."}
          </p>
        )}
      </div>

      {/* Copyable MCP Client Snippet */}
      <div className="arova-surface p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold text-white">Client Configuration Snippets</h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Copy and paste into your host AI agent configuration file.
            </p>
          </div>

          <button
            type="button"
            onClick={copySnippet}
            className="px-3 py-1.5 bg-slate-100 hover:bg-white text-slate-950 rounded text-xs font-mono font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          >
            {copied ? "Copied to Clipboard!" : "Copy MCP JSON Config"}
          </button>
        </div>

        {/* Client Tabs */}
        <div className="flex gap-1.5 border-b border-slate-800/80 pb-2">
          {(["claude", "cursor", "vscode"] as ClientTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none ${
                activeTab === tab
                  ? "bg-slate-800 text-white border border-slate-700"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab === "claude" ? "Claude Desktop" : tab === "cursor" ? "Cursor IDE" : "VS Code"}
            </button>
          ))}
        </div>

        <pre data-testid="mcp-config-code" className="bg-slate-950 p-3.5 rounded border border-slate-800/80 font-mono text-xs text-slate-200 overflow-x-auto">
          {getClientSnippet(activeTab)}
        </pre>
      </div>

      {/* Default Read-Only MCP Tools */}
      <div className="arova-surface p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold text-white">
              Default Read-Only Tools ({DEFAULT_READ_ONLY_TOOLS.length})
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Strictly read-only retrieval tools registered by default. Zero file creation, deletion, or database mutation.
            </p>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
            Active By Default
          </span>
        </div>

        <div className="space-y-2">
          {DEFAULT_READ_ONLY_TOOLS.map((tool) => (
            <div
              key={tool.name}
              data-testid={`mcp-tool-${tool.name}`}
              className="border border-slate-800/80 bg-slate-900/40 rounded p-2.5 space-y-1"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-medium text-emerald-400">
                  {tool.name}
                </span>
                <span className="text-[11px] text-slate-400">· {tool.description}</span>
              </div>

              {tool.parameters.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-0.5 font-mono text-[11px]">
                  {tool.parameters.map((p) => (
                    <span
                      key={p.name}
                      className="px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-slate-300"
                    >
                      <span className="text-slate-200">{p.name}</span>: {p.type}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Optional Write Capabilities */}
      <div className="arova-surface p-4 space-y-3 border-amber-900/40">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xs font-semibold text-white">
              Optional Write Capabilities ({OPTIONAL_WRITE_TOOLS.length})
            </h3>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Subclip export writes media files to disk. Strictly disabled by default. Requires explicit developer opt-in via <code className="font-mono text-slate-300">--enable-exports</code> or <code className="font-mono text-slate-300">AROVA_ENABLE_MCP_EXPORTS=1</code>.
            </p>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-amber-950/60 border border-amber-800/60 text-amber-300">
            Disabled by Default (Opt-In)
          </span>
        </div>

        <div className="space-y-2">
          {OPTIONAL_WRITE_TOOLS.map((tool) => (
            <div
              key={tool.name}
              data-testid={`mcp-tool-${tool.name}`}
              className="border border-amber-900/30 bg-amber-950/10 rounded p-2.5 space-y-1"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-medium text-amber-400">
                  {tool.name}
                </span>
                <span className="text-[11px] text-slate-400">· {tool.description}</span>
              </div>

              {tool.parameters.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-0.5 font-mono text-[11px]">
                  {tool.parameters.map((p) => (
                    <span
                      key={p.name}
                      className="px-1.5 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-slate-300"
                    >
                      <span className="text-slate-200">{p.name}</span>: {p.type}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

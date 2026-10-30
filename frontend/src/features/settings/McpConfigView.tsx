import { useCallback, useEffect, useState } from "react";
import { fetchMediaLibraryStats, type MediaLibraryStats } from "../../services/api";

const MCP_TOOLS = [
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

type ClientTab = "claude" | "cursor" | "antigravity";

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
            mcp: {
              servers: {
                "arova-creator-intelligence": {
                  type: "stdio",
                  command: pythonPath,
                  args: ["-m", "mcp_server.server"],
                },
              },
            },
          },
          null,
          2
        );
      case "antigravity":
        return JSON.stringify(
          {
            name: "arova-creator-intelligence",
            command: pythonPath,
            args: ["-m", "mcp_server.server"],
            transport: "stdio",
            description: "Local video RAG and multimodal retrieval engine for AI agents.",
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
    <div className="space-y-8">
      {/* Header */}
      <div className="border-b border-slate-800 pb-5">
        <h2 className="text-xl font-semibold text-white">
          Model Context Protocol (MCP) Server
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Expose your local video knowledge, transcripts, and hybrid RAG engine to Claude Desktop, Cursor, and Gemini Antigravity.
        </p>
      </div>

      {/* Live Media Stats Badge */}
      <div data-testid="mcp-live-stats" className="border border-slate-800 bg-slate-900/60 rounded-lg p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-semibold text-slate-200">
              Live Media Library Inventory
            </span>
          </div>
          <button
            type="button"
            onClick={() => void loadStats()}
            disabled={loadingStats}
            className="text-xs font-mono text-indigo-400 hover:text-indigo-300 disabled:opacity-50"
          >
            {loadingStats ? "Refreshing..." : "Refresh Stats"}
          </button>
        </div>

        {stats ? (
          <dl className="grid grid-cols-2 md:grid-cols-5 gap-3 font-mono text-xs">
            <div className="bg-slate-950/60 p-3 rounded border border-slate-800">
              <dt className="text-slate-400">Total Videos</dt>
              <dd className="text-lg font-bold text-white mt-0.5">{stats.total_videos}</dd>
            </div>
            <div className="bg-slate-950/60 p-3 rounded border border-slate-800">
              <dt className="text-slate-400">Total Duration</dt>
              <dd className="text-lg font-bold text-slate-200 mt-0.5">{stats.total_duration_sec}s</dd>
            </div>
            <div className="bg-slate-950/60 p-3 rounded border border-slate-800">
              <dt className="text-slate-400">Transcripts Indexed</dt>
              <dd className="text-lg font-bold text-indigo-400 mt-0.5">{stats.total_transcripts_indexed}</dd>
            </div>
            <div className="bg-slate-950/60 p-3 rounded border border-slate-800">
              <dt className="text-slate-400">Scene Cuts Detected</dt>
              <dd className="text-lg font-bold text-amber-400 mt-0.5">{stats.total_scene_cuts}</dd>
            </div>
            <div className="bg-slate-950/60 p-3 rounded border border-slate-800">
              <dt className="text-slate-400">Collections</dt>
              <dd className="text-lg font-bold text-slate-300 mt-0.5">{stats.total_collections}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-xs font-mono text-slate-400">
            {loadingStats ? "Querying database..." : "No video inventory detected yet."}
          </p>
        )}
      </div>

      {/* Copyable MCP Client Snippet */}
      <div className="border border-slate-800 bg-slate-900/60 rounded-lg p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white">Client Configuration Snippets</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Copy and paste into your AI agent or IDE settings file.
            </p>
          </div>

          <button
            type="button"
            onClick={copySnippet}
            className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded text-xs font-mono font-medium transition-colors"
          >
            {copied ? "Copied to Clipboard!" : "Copy MCP JSON Config"}
          </button>
        </div>

        {/* Client Tabs */}
        <div className="flex gap-2 border-b border-slate-800 pb-2">
          {(["claude", "cursor", "antigravity"] as ClientTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-1 rounded text-xs font-mono transition-colors ${
                activeTab === tab
                  ? "bg-slate-800 text-white border border-slate-700"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {tab === "claude" ? "Claude Desktop" : tab === "cursor" ? "Cursor IDE" : "Gemini Antigravity"}
            </button>
          ))}
        </div>

        <pre data-testid="mcp-config-code" className="bg-slate-950 p-4 rounded border border-slate-800 font-mono text-xs text-indigo-300 overflow-x-auto">
          {getClientSnippet(activeTab)}
        </pre>
      </div>

      {/* 8 MCP Tools Table */}
      <div className="border border-slate-800 bg-slate-900/60 rounded-lg p-5 space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-white">
            Available Read-Only MCP Tools (8)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Registered with STDIO transport and backed directly by local database and ML reranker services.
          </p>
        </div>

        <div className="space-y-3">
          {MCP_TOOLS.map((tool) => (
            <div
              key={tool.name}
              data-testid={`mcp-tool-${tool.name}`}
              className="border border-slate-800/80 bg-slate-950/40 rounded p-3 space-y-1.5"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-semibold text-emerald-400">
                  {tool.name}
                </span>
                <span className="text-[11px] text-slate-400">· {tool.description}</span>
              </div>

              {tool.parameters.length > 0 && (
                <div className="flex flex-wrap gap-2 pt-1 font-mono text-[11px]">
                  {tool.parameters.map((p) => (
                    <span
                      key={p.name}
                      className="px-2 py-0.5 rounded bg-slate-800/80 border border-slate-700/60 text-slate-300"
                    >
                      <span className="text-indigo-300">{p.name}</span>: {p.type}
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

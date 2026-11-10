import { FormEvent, useEffect, useRef, useState } from "react";
import {
  askVideoAi,
  executeSharedTool,
  fetchSharedTools,
  runEvalBenchmark,
  runSmartLoopAgent,
  searchSemantic,
  type AskQuestionResponse,
  type EvalBenchmarkReport,
  exportVideoClip,
  getClipDownloadUrl,
  getVideoStreamUrl,
  type HybridSearchResponse,
  type SharedToolDefinition,
  type SmartLoopResult,
  type ToolExecuteResult,
} from "../../services/api";

const SUGGESTIONS = [
  "vector database indexing",
  "reciprocal rank fusion",
  "cross encoder re ranking",
  "latency benchmarks",
];

const QA_PRESETS = [
  "What is covered regarding reciprocal rank fusion?",
  "What code or architecture was explained on screen?",
  "Summarize key performance numbers and latency results.",
];

export function HybridSearchView() {
  const [activeTab, setActiveTab] = useState<"search" | "smart-loop" | "tools">("search");

  // Semantic Search State
  const [query, setQuery] = useState<string>("");
  const [useReranker, setUseReranker] = useState<boolean>(true);
  const [searching, setSearching] = useState<boolean>(false);
  const [searchResponse, setSearchResponse] = useState<HybridSearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Grounded Q&A State
  const [qaQuery, setQaQuery] = useState<string>("");
  const [qaProvider, setQaProvider] = useState<string>("local");
  const [askingQa, setAskingQa] = useState<boolean>(false);
  const [qaResponse, setQaResponse] = useState<AskQuestionResponse | null>(null);
  const [qaError, setQaError] = useState<string | null>(null);

  // Channel Filter & Video Player preview
  const [channelFilter, setChannelFilter] = useState<"all" | "speech" | "visual" | "multimodal">("all");
  const [activeVideoId, setActiveVideoId] = useState<string | null>(null);
  const [activeVideoTime, setActiveVideoTime] = useState<number>(0);
  const [copiedSnippetId, setCopiedSnippetId] = useState<string | null>(null);
  const [exportingClipKey, setExportingClipKey] = useState<string | null>(null);
  const videoPlayerRef = useRef<HTMLVideoElement | null>(null);

  // ML Evaluation State
  const [evalReport, setEvalReport] = useState<EvalBenchmarkReport | null>(null);
  const [runningEval, setRunningEval] = useState<boolean>(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  // Smart Loop Agent State
  const [agentQuery, setAgentQuery] = useState<string>("");
  const [agentTurns, setAgentTurns] = useState<number>(3);
  const [runningAgent, setRunningAgent] = useState<boolean>(false);
  const [agentResult, setAgentResult] = useState<SmartLoopResult | null>(null);
  const [agentError, setAgentError] = useState<string | null>(null);

  // Shared Tool Explorer State
  const [tools, setTools] = useState<SharedToolDefinition[]>([]);
  const [selectedTool, setSelectedTool] = useState<string>("");
  const [toolArgsJson, setToolArgsJson] = useState<string>("{}");
  const [executingTool, setExecutingTool] = useState<boolean>(false);
  const [toolResult, setToolResult] = useState<ToolExecuteResult | null>(null);
  const [toolError, setToolError] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === "tools" && tools.length === 0) {
      void fetchSharedTools()
        .then((t) => {
          setTools(t);
          if (t.length > 0) {
            setSelectedTool(t[0].name);
            setToolArgsJson(JSON.stringify(t[0].parameters ? {} : {}, null, 2));
          }
        })
        .catch(() => {});
    }
  }, [activeTab, tools.length]);

  const handleExportClip = async (videoId: string, startTime: number, endTime: number) => {
    const key = `${videoId}-${startTime.toFixed(1)}-${endTime.toFixed(1)}`;
    setExportingClipKey(key);
    try {
      const resp = await exportVideoClip(videoId, startTime, endTime);
      const downloadUrl = getClipDownloadUrl(resp.clip_filename);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = resp.clip_filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Clip export failed");
    } finally {
      setExportingClipKey(null);
    }
  };

  const executeSearch = async (
    queryString: string,
    overrideChannel?: "all" | "speech" | "visual" | "multimodal"
  ) => {
    const q = queryString.trim();
    if (!q) return;
    const activeChan = overrideChannel ?? channelFilter;

    setSearching(true);
    setSearchError(null);
    try {
      const resp = await searchSemantic(q, useReranker, 10, undefined, activeChan);
      setSearchResponse(resp);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
      setSearchResponse(null);
    } finally {
      setSearching(false);
    }
  };

  const handleChannelChange = (nextChannel: "all" | "speech" | "visual" | "multimodal") => {
    setChannelFilter(nextChannel);
    if (query.trim()) {
      void executeSearch(query, nextChannel);
    }
  };

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    await executeSearch(query);
  };

  const handleAskQuestion = async (customQuestion?: string) => {
    const q = (customQuestion || qaQuery).trim();
    if (!q) return;
    if (customQuestion) setQaQuery(customQuestion);

    setAskingQa(true);
    setQaError(null);
    try {
      const resp = await askVideoAi(q, undefined, {
        channel: channelFilter,
        provider: qaProvider,
      });
      setQaResponse(resp);
    } catch (err) {
      setQaError(err instanceof Error ? err.message : "Grounded Q&A failed");
      setQaResponse(null);
    } finally {
      setAskingQa(false);
    }
  };

  const handleRunBenchmark = async () => {
    setRunningEval(true);
    setEvalError(null);
    try {
      const report = await runEvalBenchmark();
      setEvalReport(report);
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : "Benchmark failed");
    } finally {
      setRunningEval(false);
    }
  };

  const handleRunSmartLoop = async (e: FormEvent) => {
    e.preventDefault();
    if (!agentQuery.trim()) return;
    setRunningAgent(true);
    setAgentError(null);
    setAgentResult(null);
    try {
      const res = await runSmartLoopAgent({
        query: agentQuery.trim(),
        max_turns: agentTurns,
        provider: qaProvider,
      });
      setAgentResult(res);
    } catch (err) {
      setAgentError(err instanceof Error ? err.message : "Smart Loop execution failed");
    } finally {
      setRunningAgent(false);
    }
  };

  const handleExecuteTool = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedTool) return;
    setExecutingTool(true);
    setToolError(null);
    setToolResult(null);
    try {
      let parsed = {};
      try {
        parsed = JSON.parse(toolArgsJson);
      } catch {
        throw new Error("Invalid JSON in arguments field");
      }
      const res = await executeSharedTool(selectedTool, parsed);
      setToolResult(res);
    } catch (err) {
      setToolError(err instanceof Error ? err.message : "Tool execution failed");
    } finally {
      setExecutingTool(false);
    }
  };

  const jumpToClip = (videoId: string, startTime: number) => {
    setActiveVideoId(videoId);
    setActiveVideoTime(startTime);
    if (videoPlayerRef.current) {
      videoPlayerRef.current.currentTime = startTime;
      try {
        const p = videoPlayerRef.current.play();
        if (p && typeof p.catch === "function") {
          p.catch(() => {});
        }
      } catch {
        // Ignored in test environment
      }
    }
  };

  const copyQuote = (item: {
    video_id: string;
    filename: string;
    start_time: number;
    end_time: number;
    chunk_text: string;
  }) => {
    const text = `> **[${item.filename}](${getVideoStreamUrl(item.video_id)}#t=${item.start_time.toFixed(
      1
    )})** [${item.start_time.toFixed(1)}s - ${item.end_time.toFixed(1)}s]\n> "${item.chunk_text}"\n`;
    void navigator.clipboard.writeText(text);
    setCopiedSnippetId(`${item.start_time}`);
    setTimeout(() => setCopiedSnippetId(null), 2000);
  };

  const filteredResults =
    searchResponse?.results.filter((item) => {
      if (channelFilter === "all") return true;
      return item.match_channel === channelFilter;
    }) ?? [];

  return (
    <div className="space-y-6">
      {/* Top Section Nav Tabs */}
      <div className="flex items-center gap-2 border-b border-[#243149] pb-3">
        <button
          type="button"
          onClick={() => setActiveTab("search")}
          className={`px-3 py-1.5 rounded-control text-xs font-semibold font-sans transition-colors ${
            activeTab === "search"
              ? "bg-[#9B8CFF] text-[#080B12]"
              : "text-slate-400 hover:text-white bg-[#111827]"
          }`}
        >
          Semantic &amp; Hybrid Search
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("smart-loop")}
          className={`px-3 py-1.5 rounded-control text-xs font-semibold font-sans transition-colors ${
            activeTab === "smart-loop"
              ? "bg-[#9B8CFF] text-[#080B12]"
              : "text-slate-400 hover:text-white bg-[#111827]"
          }`}
        >
          Smart Loop Autonomous Agent
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("tools")}
          className={`px-3 py-1.5 rounded-control text-xs font-semibold font-sans transition-colors ${
            activeTab === "tools"
              ? "bg-[#9B8CFF] text-[#080B12]"
              : "text-slate-400 hover:text-white bg-[#111827]"
          }`}
        >
          Shared Tool Explorer ({tools.length || "13"})
        </button>
      </div>

      {/* TAB 1: SEMANTIC & HYBRID SEARCH */}
      {activeTab === "search" && (
        <div className="space-y-6">
          <div className="border-b border-[#172338] pb-5 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h2 className="text-xl font-semibold tracking-tight text-[#F5F7FB]">
                      Hybrid Video RAG &amp; Cross-Encoder Search
                    </h2>
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono text-[#51DCC8] bg-[#51DCC8]/10 border border-[#51DCC8]/30">
                      Stage-1 RRF + Stage-2 Cross-Encoder
                    </span>
                  </div>
                  <p className="text-xs text-[#A2AEC0] mt-1">
                    Dense MiniLM embeddings + BM25 Lexical FTS5 fused via Reciprocal Rank Fusion (k = 60)
                    with joint attention re-ranking.
                  </p>
                </div>

              <button
                type="button"
                onClick={handleRunBenchmark}
                disabled={runningEval}
                className="px-3.5 py-1.5 bg-[#0d1424] hover:bg-slate-800 border border-[#172338] rounded-lg text-slate-200 hover:text-white font-mono text-xs disabled:opacity-50 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
              >
                {runningEval ? "Running Golden Benchmark..." : "Run ML Evaluation Benchmark"}
              </button>
            </div>

            <form onSubmit={handleSearch} className="space-y-3">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Enter natural language query (e.g. 'explain vector database indexing')..."
                    className="w-full bg-[#090e18] border border-[#172338] rounded-lg px-3.5 py-2.5 text-xs text-slate-100 placeholder-slate-500 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none transition-colors duration-150"
                    aria-label="Search query"
                  />
                  <span className="absolute right-3 top-2.5 px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700 select-none">
                    /
                  </span>
                </div>
                <button
                  type="submit"
                  disabled={searching || !query.trim()}
                  className="px-5 py-2.5 bg-slate-100 hover:bg-white text-slate-950 rounded-lg text-xs font-semibold disabled:opacity-50 transition-colors duration-150 active:scale-95 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                >
                  {searching ? "Searching..." : "Search"}
                </button>
              </div>

              {/* Evidence Channel Scope & Reranker Toggles */}
              <div className="flex items-center justify-between flex-wrap gap-3 pt-1">
                <div
                  role="group"
                  aria-label="Evidence channel filter"
                  className="flex items-center gap-1.5 flex-wrap"
                >
                  <span className="text-[11px] font-mono text-[#6B778C] uppercase tracking-wider mr-1">
                    Retrieval Channel:
                  </span>
                  {(
                    [
                      { id: "all", label: "All Evidence" },
                      { id: "speech", label: "Spoken Dialogue Only" },
                      { id: "visual", label: "Visual OCR Only" },
                      { id: "multimodal", label: "Multimodal Fusion" },
                    ] as const
                  ).map((ch) => (
                    <button
                      key={ch.id}
                      type="button"
                      data-testid={`channel-filter-${ch.id}`}
                      onClick={() => handleChannelChange(ch.id)}
                      className={`px-2.5 py-1 rounded text-[11px] font-mono transition-colors ${
                        channelFilter === ch.id
                          ? "bg-[#9B8CFF] text-[#080B12] font-semibold"
                          : "bg-[#111827] text-[#A2AEC0] hover:text-[#F5F7FB] border border-[#243149]"
                      }`}
                    >
                      {ch.label}
                    </button>
                  ))}
                </div>

                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={useReranker}
                    onChange={(e) => setUseReranker(e.target.checked)}
                    className="rounded bg-[#090e18] border-[#243149] text-[#9B8CFF] focus:ring-0"
                  />
                  <span className="text-[#A2AEC0] font-mono text-[11px]">
                    Stage-2 Joint Cross-Encoder Re-ranker (ms-marco-MiniLM-L-6-v2)
                  </span>
                </label>
              </div>

              <div className="flex items-center gap-1.5 flex-wrap text-[#A2AEC0] font-mono text-[11px]">
                <span>Suggestions:</span>
                {SUGGESTIONS.map((sug) => (
                  <button
                    key={sug}
                    type="button"
                    onClick={() => {
                      setQuery(sug);
                      void executeSearch(sug);
                    }}
                    className="px-2 py-0.5 rounded bg-[#0d1424] hover:bg-[#172235] border border-[#243149] text-slate-300 transition-colors"
                  >
                    {sug}
                  </button>
                ))}
              </div>
            </form>
          </div>

          {searchError && (
            <div className="p-3 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-xs font-mono">
              {searchError}
            </div>
          )}

          {evalError && (
            <div className="p-3 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-xs font-mono">
              {evalError}
            </div>
          )}

          {activeVideoId && (
            <div className="p-3 rounded-panel bg-[#111827] border border-[#243149] space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span>Previewing clip @ {activeVideoTime.toFixed(1)}s</span>
                <button
                  type="button"
                  onClick={() => setActiveVideoId(null)}
                  className="text-slate-400 hover:text-white text-xs font-mono"
                >
                  &times; Close Preview
                </button>
              </div>
              <video
                ref={videoPlayerRef}
                controls
                src={`${getVideoStreamUrl(activeVideoId)}#t=${activeVideoTime}`}
                className="w-full max-h-64 object-contain rounded bg-black"
              />
            </div>
          )}

          {/* ML Benchmark Report */}
          {evalReport && (
            <div
              data-testid="eval-benchmark-report"
              className="p-4 rounded-panel bg-[#111827] border border-emerald-900/60 space-y-3"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-emerald-400 font-mono">
                  Stage-1 vs Stage-2 Benchmark Evaluation Report ({evalReport.num_queries} queries)
                </h3>
                <div className="flex items-center gap-3 text-xs font-mono">
                  <span className="text-emerald-400 font-bold">
                    MRR: +{evalReport.improvement_mrr_percent.toFixed(1)}%
                  </span>
                  <span className="text-emerald-400 font-bold">
                    NDCG: +{evalReport.improvement_ndcg_percent.toFixed(1)}%
                  </span>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs border border-[#172338] rounded-lg">
                  <thead className="bg-[#090e18] text-slate-400">
                    <tr>
                      <th className="p-2 border-b border-[#172338]">Metric</th>
                      <th className="p-2 border-b border-[#172338]">Stage-1 Bi-Encoder</th>
                      <th className="p-2 border-b border-[#172338]">Stage-2 Cross-Encoder</th>
                      <th className="p-2 border-b border-[#172338]">Delta</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#172338] text-slate-300">
                    <tr>
                      <td className="p-2 font-medium text-slate-200">MRR@10</td>
                      <td className="p-2">{evalReport.stage1_biencoder_metrics.mrr_at_10.toFixed(4)}</td>
                      <td className="p-2 text-emerald-400 font-bold">
                        {evalReport.stage2_crossencoder_metrics.mrr_at_10.toFixed(4)}
                      </td>
                      <td className="p-2 font-semibold text-emerald-400">
                        +{evalReport.improvement_mrr_percent.toFixed(1)}%
                      </td>
                    </tr>
                    <tr>
                      <td className="p-2 font-medium text-slate-200">NDCG@10</td>
                      <td className="p-2">{evalReport.stage1_biencoder_metrics.ndcg_at_10.toFixed(4)}</td>
                      <td className="p-2 text-emerald-400 font-bold">
                        {evalReport.stage2_crossencoder_metrics.ndcg_at_10.toFixed(4)}
                      </td>
                      <td className="p-2 font-semibold text-emerald-400">
                        +{evalReport.improvement_ndcg_percent.toFixed(1)}%
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Search Results Section */}
          {searchResponse && (
            <div className="space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-3 text-xs text-slate-400 font-mono bg-[#0B1019] p-3 rounded-lg border border-[#243149]">
                <div className="flex items-center gap-2 flex-wrap">
                  <span>
                    Retrieved <span className="text-white font-medium">{searchResponse.total_results}</span>{" "}
                    candidate windows in <span className="text-white">{searchResponse.total_ms.toFixed(1)}ms</span>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#172235] border border-[#243149] text-[10px] text-[#9B8CFF]">
                    Scope: {channelFilter === "all" ? "All Evidence" : channelFilter === "visual" ? "Visual OCR Only" : channelFilter === "speech" ? "Spoken Dialogue Only" : "Multimodal"}
                  </span>
                  {typeof searchResponse.visual_evidence_count === "number" && (
                    <span className="text-[11px] text-[#6B778C]">
                      · Indexed OCR windows: {searchResponse.visual_evidence_count}
                    </span>
                  )}
                </div>
              </div>

              {filteredResults.length === 0 ? (
                <div className="p-8 text-center text-xs text-[#A2AEC0] font-mono bg-[#111827] rounded-panel border border-[#243149] space-y-2">
                  <div className="text-[#F5F7FB] font-semibold">
                    No matching video chunks found for &quot;{searchResponse.query}&quot;
                    {channelFilter !== "all" ? ` in channel "${channelFilter}"` : ""}.
                  </div>
                  {channelFilter === "visual" && searchResponse.visual_evidence_count === 0 && (
                    <p className="text-[11px] text-[#F4BF69] max-w-xl mx-auto">
                      No on-screen visual OCR text has been extracted for your indexed videos yet (or Tesseract OCR was unavailable during scene indexing). Switch to &quot;All Evidence&quot; or &quot;Spoken Dialogue Only&quot; to search speech transcripts.
                    </p>
                  )}
                </div>
              ) : (
                <div className="space-y-2.5">
                  {filteredResults.map((item, idx) => {
                    const ch = item.match_channel || "speech";
                    return (
                      <div
                        key={item.embedding_id || idx}
                        className="p-4 rounded-panel bg-[#111827] border border-[#243149] space-y-2.5 hover:border-[#334366] transition-colors"
                      >
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-xs text-[#F5F7FB]">{item.filename}</span>
                            <span className="px-2 py-0.5 rounded bg-[#080B12] border border-[#243149] text-[11px] font-mono text-[#51DCC8]">
                              [{item.start_time.toFixed(1)}s - {item.end_time.toFixed(1)}s]
                            </span>
                            <span
                              data-testid={`result-channel-badge-${idx}`}
                              className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase tracking-wider border ${
                                ch === "visual"
                                  ? "bg-[#6BCBFF]/10 text-[#6BCBFF] border-[#6BCBFF]/30"
                                  : ch === "multimodal"
                                  ? "bg-[#9B8CFF]/10 text-[#9B8CFF] border-[#9B8CFF]/30"
                                  : "bg-[#51DCC8]/10 text-[#51DCC8] border-[#51DCC8]/30"
                              }`}
                            >
                              {ch === "visual"
                                ? "Visual OCR"
                                : ch === "multimodal"
                                ? "Multimodal (Speech + OCR)"
                                : "Spoken Dialogue"}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-[11px] font-mono text-slate-400">
                              RRF: <span className="text-slate-200">{item.stage1_score.toFixed(4)}</span>
                            </span>
                            <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/60 font-semibold">
                              {item.rerank_score.toFixed(4)}
                            </span>
                            <button
                              type="button"
                              onClick={() => jumpToClip(item.video_id, item.start_time)}
                              className="px-2.5 py-1 bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] rounded text-xs font-mono font-semibold"
                            >
                              Play Preview
                            </button>
                            <button
                              type="button"
                              onClick={() => copyQuote(item)}
                              className="px-2.5 py-1 bg-[#172235] hover:bg-[#1e2c44] text-slate-200 rounded text-xs font-mono border border-[#243149]"
                            >
                              {copiedSnippetId === `${item.start_time}` ? "Copied!" : "Copy Quote"}
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleExportClip(item.video_id, item.start_time, item.end_time)}
                              disabled={exportingClipKey === `${item.video_id}-${item.start_time.toFixed(1)}-${item.end_time.toFixed(1)}`}
                              className="px-2.5 py-1 bg-emerald-950/80 hover:bg-emerald-900 text-emerald-300 rounded text-xs font-mono border border-emerald-800/80 disabled:opacity-50"
                            >
                              {exportingClipKey === `${item.video_id}-${item.start_time.toFixed(1)}-${item.end_time.toFixed(1)}` ? "Exporting..." : "Export Clip"}
                            </button>
                          </div>
                        </div>

                        <p className="text-xs text-slate-300 leading-relaxed font-sans bg-[#080B12] p-2.5 rounded border border-[#243149] whitespace-pre-line">
                          &quot;{item.chunk_text}&quot;
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Grounded Q&A Section */}
          <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-3 border-b border-[#243149] pb-3">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-semibold text-[#F5F7FB]">
                    Grounded Video Q&amp;A (Citations Linked to Timestamp)
                  </h3>
                  <span
                    data-testid="qa-active-channel-badge"
                    className="px-2 py-0.5 rounded bg-[#172235] border border-[#243149] text-[10px] font-mono text-[#51DCC8]"
                  >
                    Evidence Scope: {channelFilter === "all" ? "All Evidence" : channelFilter === "visual" ? "Visual OCR Only" : channelFilter === "speech" ? "Spoken Dialogue Only" : "Multimodal"}
                  </span>
                </div>
                <p className="text-xs text-[#A2AEC0] mt-0.5">
                  Synthesize verifiable answers strictly backed by retrieved video evidence within the active retrieval channel.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-slate-400">Provider:</span>
                <select
                  aria-label="Q&A AI Provider"
                  value={qaProvider}
                  onChange={(e) => setQaProvider(e.target.value)}
                  className="px-2 py-1 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
                >
                  <option value="local">local (100% on-device)</option>
                  <option value="google-gemini">google-gemini</option>
                  <option value="openai">openai</option>
                  <option value="anthropic">anthropic</option>
                </select>
              </div>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                aria-label="Grounded Q&A question"
                value={qaQuery}
                onChange={(e) => setQaQuery(e.target.value)}
                placeholder="Ask any question about your media archive..."
                className="flex-1 px-3 py-2 rounded bg-[#0B1019] border border-[#243149] text-xs text-white focus:outline-none"
              />
              <button
                type="button"
                onClick={() => handleAskQuestion()}
                disabled={askingQa || !qaQuery.trim()}
                className="px-4 py-2 rounded bg-[#9B8CFF] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50"
              >
                {askingQa ? "Answering..." : "Ask AI"}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono text-slate-400">
              <span>Presets:</span>
              {QA_PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => void handleAskQuestion(p)}
                  className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149] transition-colors"
                >
                  {p}
                </button>
              ))}
            </div>

            {qaError && (
              <div className="p-2 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-xs font-mono">
                {qaError}
              </div>
            )}

            {qaResponse && (
              <div className="p-4 rounded bg-[#0B1019] border border-[#243149] space-y-3 text-xs">
                <div className="flex items-center justify-between flex-wrap gap-2 text-[#9B8CFF] font-semibold">
                  <span>Synthesized Grounded Answer</span>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400">
                    {qaResponse.channel_filter && (
                      <span className="px-1.5 py-0.5 rounded bg-[#172235] text-[#51DCC8] border border-[#243149]">
                        Channel: {qaResponse.channel_filter}
                      </span>
                    )}
                    <span>{qaResponse.model_name}</span>
                  </div>
                </div>
                <p className="text-slate-200 leading-relaxed font-sans whitespace-pre-line">{qaResponse.answer}</p>

                {qaResponse.citations?.length > 0 && (
                  <div className="pt-2 border-t border-[#243149] space-y-1.5">
                    <span className="text-[11px] font-mono text-slate-400">
                      Grounding Citations (click timestamp to preview clip):
                    </span>
                    {qaResponse.citations.map((c, i) => (
                      <div
                        key={i}
                        className="p-2.5 rounded bg-[#111827] border border-[#243149] flex items-center justify-between flex-wrap gap-2 font-mono text-[11px]"
                      >
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[9px] uppercase shrink-0 border ${
                              c.match_channel === "visual"
                                ? "bg-[#6BCBFF]/10 text-[#6BCBFF] border-[#6BCBFF]/30"
                                : c.match_channel === "multimodal"
                                ? "bg-[#9B8CFF]/10 text-[#9B8CFF] border-[#9B8CFF]/30"
                                : "bg-[#51DCC8]/10 text-[#51DCC8] border-[#51DCC8]/30"
                            }`}
                          >
                            {c.match_channel || "speech"}
                          </span>
                          <span className="text-slate-300 truncate">{c.snippet}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => jumpToClip(c.video_id, c.start_time)}
                          className="px-2 py-0.5 rounded bg-[#172235] hover:bg-[#9B8CFF] hover:text-[#080B12] text-[#51DCC8] border border-[#243149] transition-colors shrink-0"
                        >
                          &#9654; {c.filename} [{c.timestamp_label}]
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: SMART LOOP AUTONOMOUS AGENT */}
      {activeTab === "smart-loop" && (
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#9B8CFF]/10 text-[#9B8CFF] border border-[#9B8CFF]/30">
                STEP 7 MULTI-TURN AGENT
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
                AUTONOMOUS REASONING LOOP
              </span>
            </div>
            <h2 className="text-lg font-semibold text-[#F5F7FB] mt-1">Smart Loop Agent Runner</h2>
            <p className="text-xs text-[#A2AEC0]">
              Goal-directed multi-turn tool execution loop. The agent reasons, selects tools (search, transcript,
              metadata, clips), executes them autonomously, and synthesizes grounded answers.
            </p>
          </div>

          <form onSubmit={handleRunSmartLoop} className="space-y-3 font-sans">
            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Goal Instruction / Query:</label>
              <textarea
                rows={3}
                required
                value={agentQuery}
                onChange={(e) => setAgentQuery(e.target.value)}
                placeholder="e.g. Find where the speaker introduces the vector database, verify the exact timecode, and summarize the key argument."
                className="w-full px-3 py-2 rounded bg-[#0B1019] border border-[#243149] text-xs text-white focus:outline-none font-sans"
              />
            </div>

            <div className="flex items-center gap-4 text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className="text-slate-400">Max Iterations:</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={agentTurns}
                  onChange={(e) => setAgentTurns(parseInt(e.target.value, 10))}
                  className="w-16 px-2 py-1 rounded bg-[#0B1019] border border-[#243149] text-white"
                />
              </div>
              <button
                type="submit"
                disabled={runningAgent || !agentQuery.trim()}
                className="px-5 py-2 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50"
              >
                {runningAgent ? "Executing Autonomous Loop..." : "Run Smart Loop Agent"}
              </button>
            </div>
          </form>

          {agentError && (
            <div className="p-3 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-xs font-mono">
              {agentError}
            </div>
          )}

          {agentResult && (
            <div className="space-y-4 pt-3 border-t border-[#243149]">
              <div className="p-4 rounded bg-[#0B1019] border border-[#243149] space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-[#51DCC8]">
                  <span>Autonomous Synthesis Final Answer</span>
                  <span className="text-[10px] font-mono text-slate-400">
                    {agentResult.total_steps} Steps &middot; {agentResult.latency_ms.toFixed(0)}ms
                  </span>
                </div>
                <p className="text-xs text-slate-200 leading-relaxed font-sans">{agentResult.final_answer}</p>
              </div>

              {/* Multi-turn Execution Steps */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-300 font-mono">Autonomous Execution Trace</h3>
                <div className="space-y-2">
                  {agentResult.steps.map((st) => (
                    <div
                      key={st.step}
                      className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-1.5 text-xs font-mono"
                    >
                      <div className="flex items-center justify-between text-[#9B8CFF]">
                        <span className="font-semibold">
                          Step #{st.step}: Executed {st.tool}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Arguments: {JSON.stringify(st.arguments)}
                      </div>
                      <p className="text-slate-300 font-sans text-xs bg-[#111827] p-2 rounded border border-[#243149]">
                        {st.result_summary}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: SHARED TOOL EXPLORER */}
      {activeTab === "tools" && (
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30">
                SHARED TOOL EXECUTION ENGINE
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
                READ-ONLY AGENT TOOLS
              </span>
            </div>
            <h2 className="text-lg font-semibold text-[#F5F7FB] mt-1">Shared Tool Catalog &amp; Console</h2>
            <p className="text-xs text-[#A2AEC0]">
              Shared tool execution runtime unified across AI Agents, FastMCP, and the Workstation UI.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Tool Selection List */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-slate-300">Registered Tools ({tools.length})</h3>
              <div className="space-y-1 max-h-96 overflow-y-auto">
                {tools.map((t) => (
                  <div
                    key={t.name}
                    onClick={() => {
                      setSelectedTool(t.name);
                      setToolArgsJson(JSON.stringify({}, null, 2));
                    }}
                    className={`p-2.5 rounded cursor-pointer text-xs font-mono transition-colors ${
                      selectedTool === t.name
                        ? "bg-[#172235] text-[#9B8CFF] border border-[#9B8CFF]/40"
                        : "bg-[#0B1019] text-slate-300 hover:bg-[#172235]/60 border border-[#243149]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">{t.name}</span>
                      <span
                        className={`text-[9px] px-1 py-0.2 rounded uppercase ${
                          t.read_only ? "bg-emerald-950 text-emerald-300" : "bg-amber-950 text-amber-300"
                        }`}
                      >
                        {t.read_only ? "Read Only" : "Gated Write"}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1 truncate">{t.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Tool Runner Console */}
            <div className="lg:col-span-2 space-y-4">
              {selectedTool ? (
                <form onSubmit={handleExecuteTool} className="space-y-3 font-sans">
                  <div className="flex items-center justify-between text-xs border-b border-[#243149] pb-2">
                    <span className="font-semibold text-white font-mono">Execute: {selectedTool}</span>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs text-slate-300 font-mono">Arguments JSON Payload:</label>
                    <textarea
                      rows={4}
                      value={toolArgsJson}
                      onChange={(e) => setToolArgsJson(e.target.value)}
                      className="w-full px-3 py-2 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8] focus:outline-none"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={executingTool}
                    className="px-4 py-1.5 rounded bg-[#9B8CFF] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50"
                  >
                    {executingTool ? "Executing Tool..." : "Run Tool In Enclave"}
                  </button>

                  {toolResult && (
                    <div className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-1 text-xs font-mono">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[#51DCC8] font-semibold">Result</span>
                        <span>Latency: {toolResult.latency_ms.toFixed(1)}ms</span>
                      </div>
                      <pre className="p-2 rounded bg-[#080B12] text-slate-200 overflow-x-auto max-h-60 text-[11px]">
                        {JSON.stringify(toolResult.result, null, 2)}
                      </pre>
                    </div>
                  )}

                  {toolError && (
                    <div className="p-2.5 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-xs font-mono">
                      {toolError}
                    </div>
                  )}
                </form>
              ) : (
                <div className="p-8 text-center text-xs text-slate-500 font-mono">
                  Select a tool on the left to inspect its parameters and execute it.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

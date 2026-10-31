import { FormEvent, useRef, useState } from "react";
import {
  askVideoAi,
  type AskQuestionResponse,
  type EvalBenchmarkReport,
  getVideoStreamUrl,
  type HybridSearchResponse,
  runEvalBenchmark,
  searchSemantic,
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
  const [query, setQuery] = useState<string>("");
  const [useReranker, setUseReranker] = useState<boolean>(true);
  const [searching, setSearching] = useState<boolean>(false);
  const [searchResponse, setSearchResponse] = useState<HybridSearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [qaQuery, setQaQuery] = useState<string>("");
  const [askingQa, setAskingQa] = useState<boolean>(false);
  const [qaResponse, setQaResponse] = useState<AskQuestionResponse | null>(null);
  const [qaError, setQaError] = useState<string | null>(null);

  const [channelFilter, setChannelFilter] = useState<"all" | "speech" | "visual" | "multimodal">("all");

  const [evalReport, setEvalReport] = useState<EvalBenchmarkReport | null>(null);
  const [runningEval, setRunningEval] = useState<boolean>(false);
  const [evalError, setEvalError] = useState<string | null>(null);

  const [activeVideoId, setActiveVideoId] = useState<string | null>(null);
  const [activeVideoTime, setActiveVideoTime] = useState<number>(0);
  const [copiedSnippetId, setCopiedSnippetId] = useState<string | null>(null);
  const videoPlayerRef = useRef<HTMLVideoElement | null>(null);

  const executeSearch = async (queryString: string) => {
    const q = queryString.trim();
    if (!q) return;

    setSearching(true);
    setSearchError(null);
    try {
      const resp = await searchSemantic(q, useReranker, 10);
      setSearchResponse(resp);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
      setSearchResponse(null);
    } finally {
      setSearching(false);
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
      const resp = await askVideoAi(q);
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

  const copyQuote = (item: { video_id: string; filename: string; start_time: number; end_time: number; chunk_text: string }) => {
    const text = `> **[${item.filename}](${getVideoStreamUrl(item.video_id)}#t=${item.start_time.toFixed(1)})** [${item.start_time.toFixed(1)}s - ${item.end_time.toFixed(1)}s]\n> "${item.chunk_text}"\n`;
    void navigator.clipboard.writeText(text);
    setCopiedSnippetId(`${item.start_time}`);
    setTimeout(() => setCopiedSnippetId(null), 2000);
  };

  const filteredResults = searchResponse?.results.filter((item) => {
    if (channelFilter === "all") return true;
    return item.match_channel === channelFilter;
  }) ?? [];

  return (
    <div className="space-y-6">
      {/* Search Header & Query Form */}
      <div className="border-b border-[#172338] pb-5 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-xl font-semibold tracking-tight text-slate-100">
                Hybrid Video RAG &amp; Cross-Encoder Search
              </h2>
              <span className="px-2 py-0.5 rounded text-[11px] font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/60">
                Stage-1 RRF + Stage-2 Cross-Encoder
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Dense MiniLM embeddings + BM25 Lexical FTS5 fused via Reciprocal Rank Fusion ($k=60$) with joint attention re-ranking.
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

          {/* Quick Query Suggestion Chips & Stage-2 Toggle */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-0.5">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-mono text-slate-500">Suggestions:</span>
              {SUGGESTIONS.map((sug) => (
                <button
                  key={sug}
                  type="button"
                  onClick={() => {
                    setQuery(sug);
                    void executeSearch(sug);
                  }}
                  className="px-2 py-0.5 rounded bg-[#090e18] hover:bg-slate-800 border border-[#172338] text-[11px] font-mono text-slate-400 hover:text-slate-200 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                >
                  {sug}
                </button>
              ))}
            </div>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useReranker}
                onChange={(e) => setUseReranker(e.target.checked)}
                className="rounded border-slate-700 bg-slate-800 text-slate-200 focus-visible:ring-2 focus-visible:ring-slate-400"
              />
              <span className="text-xs">Enable Stage-2 Cross-Encoder Re-Ranking</span>
            </label>
          </div>
        </form>
      </div>

      {/* Grounded Video Q&A Assistant Bar */}
      <div className="hallmark-surface p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-cyan-400" />
            <span className="text-xs font-semibold text-slate-200">
              Ask Video Archive (Grounded AI Q&amp;A)
            </span>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Strictly cites real timecodes with live video seek
          </span>
        </div>

        {/* Preset Question Pills */}
        <div className="flex flex-wrap gap-1.5">
          {QA_PRESETS.map((p, i) => (
            <button
              key={i}
              type="button"
              onClick={() => void handleAskQuestion(p)}
              className="px-2.5 py-1 rounded bg-[#060911] hover:bg-[#0d1424] border border-[#172338] text-[11px] font-mono text-slate-300 hover:text-white transition-colors"
            >
              &quot;{p}&quot;
            </button>
          ))}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); void handleAskQuestion(); }} className="flex gap-2">
          <input
            type="text"
            value={qaQuery}
            onChange={(e) => setQaQuery(e.target.value)}
            placeholder="Ask anything about what was spoken or shown on screen..."
            aria-label="Ask video question"
            className="flex-1 bg-[#090e18] border border-[#172338] rounded-lg px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          />
          <button
            type="submit"
            disabled={askingQa || !qaQuery.trim()}
            className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium disabled:opacity-50 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          >
            {askingQa ? "Synthesizing..." : "Ask Archive"}
          </button>
        </form>

        {qaError && (
          <div className="border border-rose-900/50 bg-rose-950/20 rounded-lg p-3 text-xs text-rose-300 font-mono">
            {qaError}
          </div>
        )}

        {qaResponse && (
          <div className="p-3.5 rounded-lg border border-[#172338] bg-[#090e18] space-y-2.5">
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 border-b border-[#172338] pb-1.5">
              <span>Answer grounded in {qaResponse.citations.length} video segment(s)</span>
              <span className="text-emerald-400">Model: {qaResponse.model_name}</span>
            </div>
            <p className="text-xs text-slate-200 leading-relaxed font-sans whitespace-pre-line">
              {qaResponse.answer}
            </p>
            {qaResponse.citations.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <span className="text-[11px] font-mono text-slate-400 block">Video Citations:</span>
                <div className="flex flex-wrap gap-2">
                  {qaResponse.citations.map((c, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => jumpToClip(c.video_id, c.start_time)}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#0d1424] hover:bg-slate-800 border border-[#172338] text-[11px] font-mono text-slate-300 hover:text-white transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                    >
                      <span className="text-emerald-400 font-medium">[{c.timestamp_label}]</span>
                      <span className="truncate max-w-[140px]">{c.filename}</span>
                      <span className="text-[10px] text-slate-500">({c.match_channel})</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Errors */}
      {searchError && (
        <div className="border border-rose-900/50 bg-rose-950/20 rounded-lg p-3 text-xs text-rose-300 font-mono flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
          <span>{searchError}</span>
        </div>
      )}

      {evalError && (
        <div className="border border-rose-900/50 bg-rose-950/20 rounded-lg p-3 text-xs text-rose-300 font-mono flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
          <span>{evalError}</span>
        </div>
      )}

      {/* Video Player Preview HUD (Floating / Side-by-Side) */}
      {activeVideoId && (
        <div className="hallmark-surface p-4 space-y-3">
          <div className="flex items-center justify-between text-xs font-mono text-slate-300">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Studio Clip Preview at {activeVideoTime.toFixed(1)}s</span>
            </div>
            <button
              type="button"
              onClick={() => setActiveVideoId(null)}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] font-mono border border-slate-700 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
            >
              Close
            </button>
          </div>
          <video
            ref={videoPlayerRef}
            src={getVideoStreamUrl(activeVideoId)}
            controls
            autoPlay
            className="w-full max-h-96 rounded-lg bg-black border border-[#172338]"
            onLoadedMetadata={() => {
              if (videoPlayerRef.current) {
                videoPlayerRef.current.currentTime = activeVideoTime;
              }
            }}
          />
        </div>
      )}

      {/* ML Evaluation Benchmark Results Table */}
      {evalReport && (
        <div data-testid="eval-benchmark-report" className="hallmark-surface p-5 space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-xs font-semibold text-slate-100">
                ML Evaluation Benchmark: Stage-1 (Bi-Encoder) vs Stage-2 (Cross-Encoder)
              </h3>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Evaluated across {evalReport.num_queries} golden test queries with ground-truth relevance.
              </p>
            </div>
            <div className="flex gap-2 font-mono text-xs">
              <span className="px-2.5 py-0.5 rounded bg-emerald-950/80 border border-emerald-800 text-emerald-400">
                MRR: +{evalReport.improvement_mrr_percent.toFixed(1)}%
              </span>
              <span className="px-2.5 py-0.5 rounded bg-[#090e18] border border-[#172338] text-slate-300">
                NDCG: +{evalReport.improvement_ndcg_percent.toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs border border-[#172338] rounded-lg overflow-hidden">
              <thead className="bg-[#090e18] text-slate-400 text-xs">
                <tr>
                  <th className="p-2.5 border-b border-[#172338] font-medium">Metric</th>
                  <th className="p-2.5 border-b border-[#172338] font-medium">Stage-1 (Bi-Encoder + FTS5)</th>
                  <th className="p-2.5 border-b border-[#172338] font-medium">Stage-2 (Cross-Encoder Re-ranked)</th>
                  <th className="p-2.5 border-b border-[#172338] font-medium">Relative Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#172338] text-slate-300">
                <tr className="bg-[#060911]/40">
                  <td className="p-2.5 font-medium text-slate-200">MRR@10</td>
                  <td className="p-2.5">{evalReport.stage1_biencoder_metrics.mrr_at_10.toFixed(4)}</td>
                  <td className="p-2.5 text-emerald-400 font-bold">{evalReport.stage2_crossencoder_metrics.mrr_at_10.toFixed(4)}</td>
                  <td className="p-2.5 font-semibold text-emerald-400">+{evalReport.improvement_mrr_percent.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-slate-200">NDCG@10</td>
                  <td className="p-2.5">{evalReport.stage1_biencoder_metrics.ndcg_at_10.toFixed(4)}</td>
                  <td className="p-2.5 text-emerald-400 font-bold">{evalReport.stage2_crossencoder_metrics.ndcg_at_10.toFixed(4)}</td>
                  <td className="p-2.5 font-semibold text-emerald-400">+{evalReport.improvement_ndcg_percent.toFixed(1)}%</td>
                </tr>
                <tr className="bg-[#060911]/40">
                  <td className="p-2.5">Recall@1</td>
                  <td className="p-2.5">{evalReport.stage1_biencoder_metrics.recall_at_1.toFixed(4)}</td>
                  <td className="p-2.5">{evalReport.stage2_crossencoder_metrics.recall_at_1.toFixed(4)}</td>
                  <td className="p-2.5">-</td>
                </tr>
                <tr>
                  <td className="p-2.5">Recall@3</td>
                  <td className="p-2.5">{evalReport.stage1_biencoder_metrics.recall_at_3.toFixed(4)}</td>
                  <td className="p-2.5">{evalReport.stage2_crossencoder_metrics.recall_at_3.toFixed(4)}</td>
                  <td className="p-2.5">-</td>
                </tr>
                <tr className="bg-[#060911]/40">
                  <td className="p-2.5">Recall@5</td>
                  <td className="p-2.5">{evalReport.stage1_biencoder_metrics.recall_at_5.toFixed(4)}</td>
                  <td className="p-2.5">{evalReport.stage2_crossencoder_metrics.recall_at_5.toFixed(4)}</td>
                  <td className="p-2.5">-</td>
                </tr>
                <tr>
                  <td className="p-2.5">Recall@10</td>
                  <td className="p-2.5">{evalReport.stage1_biencoder_metrics.recall_at_10.toFixed(4)}</td>
                  <td className="p-2.5">{evalReport.stage2_crossencoder_metrics.recall_at_10.toFixed(4)}</td>
                  <td className="p-2.5">-</td>
                </tr>
                <tr className="bg-[#060911]/40">
                  <td className="p-2.5">Latency p50 / p95 (ms)</td>
                  <td className="p-2.5">
                    {evalReport.stage1_latency_ms.p50.toFixed(1)} / {evalReport.stage1_latency_ms.p95.toFixed(1)} ms
                  </td>
                  <td className="p-2.5 text-slate-300">
                    {evalReport.stage2_latency_ms.p50.toFixed(1)} / {evalReport.stage2_latency_ms.p95.toFixed(1)} ms
                  </td>
                  <td className="p-2.5 text-slate-400">Joint Cross-Attention</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Search Results Section */}
      {searchResponse && (
        <div className="space-y-3">
          {/* Results Summary Bar + Channel Filters */}
          <div className="flex items-center justify-between flex-wrap gap-3 text-xs text-slate-400 font-mono bg-[#090e18] p-3 rounded-lg border border-[#172338]">
            <div className="flex items-center gap-2">
              <span>
                Retrieved <span className="text-white font-medium">{searchResponse.total_results}</span> candidate windows in <span className="text-white">{searchResponse.total_ms.toFixed(1)}ms</span>
              </span>
              <span className="text-slate-600">·</span>
              <span className="text-[11px] text-slate-500">
                Stage-1: {searchResponse.stage1_ms.toFixed(1)}ms · Stage-2 Rerank: {searchResponse.stage2_rerank_ms.toFixed(1)}ms
              </span>
            </div>

            {/* Channel Filters */}
            <div className="flex items-center gap-1">
              <span className="text-slate-500 text-[11px] mr-1">Channel:</span>
              {(["all", "speech", "visual", "multimodal"] as const).map((ch) => (
                <button
                  key={ch}
                  type="button"
                  onClick={() => setChannelFilter(ch)}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono transition-colors ${
                    channelFilter === ch
                      ? "bg-slate-100 text-slate-950 font-bold"
                      : "text-slate-400 hover:text-slate-200 bg-[#0d1424]"
                  }`}
                >
                  {ch === "all" ? "All Channels" : ch === "visual" ? "Visual OCR" : ch === "speech" ? "Speech ASR" : "Multimodal"}
                </button>
              ))}
            </div>
          </div>

          {filteredResults.length === 0 ? (
            <div className="hallmark-surface border-dashed border-[#172338] p-8 text-center text-xs text-slate-400 space-y-1">
              <p className="font-medium text-slate-300">No matching video chunks found for &quot;{searchResponse.query}&quot;.</p>
              <p className="text-[11px] text-slate-500 font-mono">Try indexing more videos or broadening your query.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {filteredResults.map((item, idx) => (
                <div
                  key={item.embedding_id || idx}
                  className="hallmark-surface p-4 space-y-2.5 hover:border-[#253654] transition-colors"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-xs text-white">{item.filename}</span>
                      <span className="px-2 py-0.5 rounded bg-[#060911] border border-[#172338] text-[11px] font-mono text-slate-300">
                        [{item.start_time.toFixed(1)}s - {item.end_time.toFixed(1)}s]
                      </span>
                      {item.match_channel === "visual" ? (
                        <span className="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-800/60 text-[10px] font-mono text-cyan-300">
                          Visual OCR
                        </span>
                      ) : item.match_channel === "multimodal" ? (
                        <span className="px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-800/60 text-[10px] font-mono text-emerald-300">
                          Multimodal
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-[#060911] border border-[#172338] text-[10px] font-mono text-slate-400">
                          Speech ASR
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2.5">
                      <span className="text-[11px] font-mono text-slate-400">
                        RRF: <span className="text-slate-200">{item.stage1_score.toFixed(4)}</span>
                      </span>
                      <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/60">
                        Cross-Encoder: <span className="font-semibold">{item.rerank_score.toFixed(4)}</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => jumpToClip(item.video_id, item.start_time)}
                        className="px-2.5 py-1 bg-slate-100 hover:bg-white text-slate-950 rounded text-xs font-mono font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                      >
                        Play Preview
                      </button>
                      <button
                        type="button"
                        onClick={() => copyQuote(item)}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded text-xs font-mono border border-slate-700 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                      >
                        {copiedSnippetId === `${item.start_time}` ? "Copied!" : "Copy Quote"}
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed font-sans bg-[#060911] p-2.5 rounded border border-[#172338]">
                    &quot;{item.chunk_text}&quot;
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

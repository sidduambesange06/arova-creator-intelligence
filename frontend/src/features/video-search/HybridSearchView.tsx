import { FormEvent, useRef, useState } from "react";
import {
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

export function HybridSearchView() {
  const [query, setQuery] = useState<string>("");
  const [useReranker, setUseReranker] = useState<boolean>(true);
  const [searching, setSearching] = useState<boolean>(false);
  const [searchResponse, setSearchResponse] = useState<HybridSearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

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

  return (
    <div className="space-y-8 animate-fadeIn">
      {/* Search Header & Hero Input */}
      <div className="border-b border-slate-800/80 pb-6 space-y-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-2xl font-bold tracking-tight text-white">
              Hybrid Video RAG &amp; Cross-Encoder Search
            </h2>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Two-Stage RRF
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Stage-1 Dense vector + BM25 Lexical RRF Fusion followed by Stage-2 Cross-Encoder joint ML re-ranking.
          </p>
        </div>

        <form onSubmit={handleSearch} className="space-y-3">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Enter natural language query (e.g. 'explain vector database indexing')..."
                className="w-full bg-slate-950/80 border border-slate-700/80 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all shadow-inner"
                aria-label="Search query"
              />
              <span className="absolute right-3.5 top-3.5 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700 select-none">
                /
              </span>
            </div>
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="px-6 py-3 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-indigo-600/20 active:scale-95"
            >
              {searching ? "Searching..." : "Search"}
            </button>
          </div>

          {/* Quick Query Suggestion Chips */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-[11px] font-mono text-slate-400">Suggestions:</span>
            {SUGGESTIONS.map((sug) => (
              <button
                key={sug}
                type="button"
                onClick={() => {
                  setQuery(sug);
                  void executeSearch(sug);
                }}
                className="px-2.5 py-1 rounded-full bg-slate-900/80 hover:bg-indigo-950/60 hover:text-indigo-300 border border-slate-800 text-[11px] font-mono text-slate-400 transition-colors"
              >
                {sug}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useReranker}
                onChange={(e) => setUseReranker(e.target.checked)}
                className="rounded border-slate-700 bg-slate-800 text-indigo-500 focus:ring-indigo-500"
              />
              <span className="font-medium">Enable Stage-2 Cross-Encoder Re-Ranking</span>
            </label>

            <button
              type="button"
              onClick={handleRunBenchmark}
              disabled={runningEval}
              className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-300 hover:text-white font-mono text-xs disabled:opacity-50 transition-all shadow-sm"
            >
              {runningEval ? "Running Golden Benchmark..." : "Run ML Evaluation Benchmark"}
            </button>
          </div>
        </form>
      </div>

      {/* Errors */}
      {searchError && (
        <div className="border border-rose-900/50 bg-rose-950/30 rounded-xl p-4 text-xs text-rose-300 font-mono flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-rose-400" />
          <span>{searchError}</span>
        </div>
      )}

      {evalError && (
        <div className="border border-rose-900/50 bg-rose-950/30 rounded-xl p-4 text-xs text-rose-300 font-mono flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-rose-400" />
          <span>{evalError}</span>
        </div>
      )}

      {/* Video Player Modal / Preview */}
      {activeVideoId && (
        <div className="glass-panel rounded-2xl p-5 space-y-3 shadow-2xl border-indigo-900/40">
          <div className="flex items-center justify-between text-xs font-mono text-slate-300">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Preview Clip at {activeVideoTime.toFixed(1)}s</span>
            </div>
            <button
              type="button"
              onClick={() => setActiveVideoId(null)}
              className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px]"
            >
              ✕ Close Preview
            </button>
          </div>
          <video
            ref={videoPlayerRef}
            src={getVideoStreamUrl(activeVideoId)}
            controls
            autoPlay
            className="w-full max-h-80 rounded-xl bg-black border border-slate-800"
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
        <div data-testid="eval-benchmark-report" className="glass-panel rounded-2xl p-6 space-y-4 shadow-xl border-slate-800">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span>ML Evaluation Benchmark: Stage-1 (Bi-Encoder) vs Stage-2 (Cross-Encoder)</span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluated across {evalReport.num_queries} golden test queries with ground-truth relevance.
              </p>
            </div>
            <div className="flex gap-2 font-mono text-xs">
              <span className="px-3 py-1 rounded-full bg-emerald-950/80 border border-emerald-800 text-emerald-400">
                MRR: +{evalReport.improvement_mrr_percent.toFixed(1)}%
              </span>
              <span className="px-3 py-1 rounded-full bg-indigo-950/80 border border-indigo-800 text-indigo-400">
                NDCG: +{evalReport.improvement_ndcg_percent.toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs border border-slate-800 rounded-lg overflow-hidden">
              <thead className="bg-slate-900/90 text-slate-400 uppercase text-[10px] tracking-wider">
                <tr>
                  <th className="p-3 border-b border-slate-800">Metric</th>
                  <th className="p-3 border-b border-slate-800">Stage-1 (Bi-Encoder + FTS5)</th>
                  <th className="p-3 border-b border-slate-800">Stage-2 (Cross-Encoder Re-ranked)</th>
                  <th className="p-3 border-b border-slate-800">Relative Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 text-slate-300">
                <tr className="bg-slate-950/40">
                  <td className="p-3 font-semibold text-slate-200">MRR@10</td>
                  <td className="p-3">{evalReport.stage1_biencoder_metrics.mrr_at_10.toFixed(4)}</td>
                  <td className="p-3 text-emerald-400 font-bold">{evalReport.stage2_crossencoder_metrics.mrr_at_10.toFixed(4)}</td>
                  <td className="p-3 font-semibold text-emerald-400">+{evalReport.improvement_mrr_percent.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="p-3 font-semibold text-slate-200">NDCG@10</td>
                  <td className="p-3">{evalReport.stage1_biencoder_metrics.ndcg_at_10.toFixed(4)}</td>
                  <td className="p-3 text-emerald-400 font-bold">{evalReport.stage2_crossencoder_metrics.ndcg_at_10.toFixed(4)}</td>
                  <td className="p-3 font-semibold text-emerald-400">+{evalReport.improvement_ndcg_percent.toFixed(1)}%</td>
                </tr>
                <tr className="bg-slate-950/40">
                  <td className="p-3">Recall@1</td>
                  <td className="p-3">{evalReport.stage1_biencoder_metrics.recall_at_1.toFixed(4)}</td>
                  <td className="p-3">{evalReport.stage2_crossencoder_metrics.recall_at_1.toFixed(4)}</td>
                  <td className="p-3">-</td>
                </tr>
                <tr>
                  <td className="p-3">Recall@3</td>
                  <td className="p-3">{evalReport.stage1_biencoder_metrics.recall_at_3.toFixed(4)}</td>
                  <td className="p-3">{evalReport.stage2_crossencoder_metrics.recall_at_3.toFixed(4)}</td>
                  <td className="p-3">-</td>
                </tr>
                <tr className="bg-slate-950/40">
                  <td className="p-3">Recall@5</td>
                  <td className="p-3">{evalReport.stage1_biencoder_metrics.recall_at_5.toFixed(4)}</td>
                  <td className="p-3">{evalReport.stage2_crossencoder_metrics.recall_at_5.toFixed(4)}</td>
                  <td className="p-3">-</td>
                </tr>
                <tr>
                  <td className="p-3">Recall@10</td>
                  <td className="p-3">{evalReport.stage1_biencoder_metrics.recall_at_10.toFixed(4)}</td>
                  <td className="p-3">{evalReport.stage2_crossencoder_metrics.recall_at_10.toFixed(4)}</td>
                  <td className="p-3">-</td>
                </tr>
                <tr className="bg-slate-950/40">
                  <td className="p-3">Latency p50 / p95 (ms)</td>
                  <td className="p-3">
                    {evalReport.stage1_latency_ms.p50.toFixed(1)} / {evalReport.stage1_latency_ms.p95.toFixed(1)} ms
                  </td>
                  <td className="p-3 text-indigo-300">
                    {evalReport.stage2_latency_ms.p50.toFixed(1)} / {evalReport.stage2_latency_ms.p95.toFixed(1)} ms
                  </td>
                  <td className="p-3 text-slate-400">Joint Cross-Attention</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Search Results */}
      {searchResponse && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono bg-slate-900/60 p-3 rounded-xl border border-slate-800">
            <span>
              Retrieved <span className="text-white font-semibold">{searchResponse.total_results}</span> candidate windows in <span className="text-white">{searchResponse.total_ms.toFixed(1)}ms</span>
            </span>
            <span>
              Stage-1: {searchResponse.stage1_ms.toFixed(1)}ms · Stage-2 Rerank: {searchResponse.stage2_rerank_ms.toFixed(1)}ms
            </span>
          </div>

          {searchResponse.results.length === 0 ? (
            <div className="glass-panel border-dashed border-slate-800 rounded-2xl p-10 text-center text-sm text-slate-400 space-y-1">
              <p className="font-medium text-slate-300">No matching video chunks found for &quot;{searchResponse.query}&quot;.</p>
              <p className="text-xs text-slate-500 font-mono">Try indexing more videos or broadening your query.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {searchResponse.results.map((item, idx) => (
                <div
                  key={item.embedding_id || idx}
                  className="glass-panel glass-panel-hover rounded-xl p-5 space-y-3"
                >
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className="font-bold text-sm text-white">{item.filename}</span>
                      <span className="px-2.5 py-0.5 rounded-full bg-indigo-950/80 border border-indigo-800/60 text-[11px] font-mono text-indigo-300">
                        [{item.start_time.toFixed(1)}s - {item.end_time.toFixed(1)}s]
                      </span>
                      {item.match_channel === "visual" ? (
                        <span className="px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-800/60 text-[10px] font-mono text-cyan-300">
                          🖥️ Visual Screen Match
                        </span>
                      ) : item.match_channel === "multimodal" ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-950/80 border border-emerald-800/60 text-[10px] font-mono text-emerald-300">
                          ⚡ Multimodal Match
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-slate-900 border border-slate-800 text-[10px] font-mono text-slate-400">
                          🎙️ Speech Match
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-[11px] font-mono text-slate-400">
                        RRF: <span className="text-slate-200">{item.stage1_score.toFixed(4)}</span>
                      </span>
                      <span className="text-[11px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/60">
                        Cross-Encoder: <span className="font-semibold">{item.rerank_score.toFixed(4)}</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => jumpToClip(item.video_id, item.start_time)}
                        className="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-mono font-medium transition-colors shadow-sm"
                      >
                        Play Preview
                      </button>
                      <button
                        type="button"
                        onClick={() => copyQuote(item)}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-mono transition-colors"
                      >
                        {copiedSnippetId === `${item.start_time}` ? "Copied Quote!" : "Copy Quote"}
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-slate-200 leading-relaxed font-sans bg-slate-950/60 p-3 rounded-lg border border-slate-800/80">
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

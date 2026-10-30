import { FormEvent, useRef, useState } from "react";
import {
  type EvalBenchmarkReport,
  getVideoStreamUrl,
  type HybridSearchResponse,
  runEvalBenchmark,
  searchSemantic,
} from "../../services/api";

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
  const videoPlayerRef = useRef<HTMLVideoElement | null>(null);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    const q = query.trim();
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
      void videoPlayerRef.current.play().catch(() => {});
    }
  };

  return (
    <div className="space-y-8">
      {/* Search Header & Input */}
      <div className="border-b border-slate-800 pb-5">
        <h2 className="text-xl font-semibold text-white">
          Hybrid Video RAG &amp; Cross-Encoder Search
        </h2>
        <p className="text-sm text-slate-400 mt-1">
          Stage-1 Dense + BM25 RRF Fusion followed by Stage-2 Cross-Encoder ML Re-Ranking.
        </p>

        <form onSubmit={handleSearch} className="mt-4 space-y-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter natural language query (e.g. 'explain vector database indexing')..."
              className="flex-1 bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              aria-label="Search query"
            />
            <button
              type="submit"
              disabled={searching || !query.trim()}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-md text-sm font-medium transition-colors"
            >
              {searching ? "Searching..." : "Search"}
            </button>
          </div>

          <div className="flex items-center justify-between text-xs">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={useReranker}
                onChange={(e) => setUseReranker(e.target.checked)}
                className="rounded border-slate-700 bg-slate-800 text-indigo-500 focus:ring-indigo-500"
              />
              <span>Enable Stage-2 Cross-Encoder Re-Ranking</span>
            </label>

            <button
              type="button"
              onClick={handleRunBenchmark}
              disabled={runningEval}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded text-slate-300 hover:text-white font-mono text-[11px] disabled:opacity-50"
            >
              {runningEval ? "Running Golden Benchmark..." : "Run ML Evaluation Benchmark"}
            </button>
          </div>
        </form>
      </div>

      {/* Errors */}
      {searchError && (
        <div className="border border-rose-900/50 bg-rose-950/20 rounded-md p-4 text-xs text-rose-300 font-mono">
          {searchError}
        </div>
      )}

      {evalError && (
        <div className="border border-rose-900/50 bg-rose-950/20 rounded-md p-4 text-xs text-rose-300 font-mono">
          {evalError}
        </div>
      )}

      {/* Video Player Modal / Preview */}
      {activeVideoId && (
        <div className="border border-indigo-900/40 bg-slate-900/80 rounded-lg p-4 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>Live Video Preview (Seeked to {activeVideoTime.toFixed(1)}s)</span>
            <button
              type="button"
              onClick={() => setActiveVideoId(null)}
              className="text-slate-400 hover:text-white"
            >
              Close
            </button>
          </div>
          <video
            ref={videoPlayerRef}
            src={getVideoStreamUrl(activeVideoId)}
            controls
            autoPlay
            className="w-full max-h-72 rounded bg-black"
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
        <div data-testid="eval-benchmark-report" className="border border-slate-800 bg-slate-900/50 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">
                ML Evaluation Benchmark: Stage-1 (Bi-Encoder) vs Stage-2 (Cross-Encoder)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Evaluated across {evalReport.num_queries} golden test queries with ground-truth relevance.
              </p>
            </div>
            <div className="flex gap-2">
              <span className="px-2 py-1 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-400 font-mono text-xs">
                MRR: +{evalReport.improvement_mrr_percent.toFixed(1)}%
              </span>
              <span className="px-2 py-1 rounded bg-indigo-950/60 border border-indigo-800 text-indigo-400 font-mono text-xs">
                NDCG: +{evalReport.improvement_ndcg_percent.toFixed(1)}%
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs border border-slate-800">
              <thead className="bg-slate-800/60 text-slate-400">
                <tr>
                  <th className="p-2 border-b border-slate-700">Metric</th>
                  <th className="p-2 border-b border-slate-700">Stage-1 (Bi-Encoder + FTS5)</th>
                  <th className="p-2 border-b border-slate-700">Stage-2 (Cross-Encoder Re-ranked)</th>
                  <th className="p-2 border-b border-slate-700">Relative Delta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-300">
                <tr>
                  <td className="p-2 font-medium text-slate-200">MRR@10</td>
                  <td className="p-2">{evalReport.stage1_biencoder_metrics.mrr_at_10.toFixed(4)}</td>
                  <td className="p-2 text-emerald-400">{evalReport.stage2_crossencoder_metrics.mrr_at_10.toFixed(4)}</td>
                  <td className="p-2 font-semibold text-emerald-400">+{evalReport.improvement_mrr_percent.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="p-2 font-medium text-slate-200">NDCG@10</td>
                  <td className="p-2">{evalReport.stage1_biencoder_metrics.ndcg_at_10.toFixed(4)}</td>
                  <td className="p-2 text-emerald-400">{evalReport.stage2_crossencoder_metrics.ndcg_at_10.toFixed(4)}</td>
                  <td className="p-2 font-semibold text-emerald-400">+{evalReport.improvement_ndcg_percent.toFixed(1)}%</td>
                </tr>
                <tr>
                  <td className="p-2">Recall@1</td>
                  <td className="p-2">{evalReport.stage1_biencoder_metrics.recall_at_1.toFixed(4)}</td>
                  <td className="p-2">{evalReport.stage2_crossencoder_metrics.recall_at_1.toFixed(4)}</td>
                  <td className="p-2">-</td>
                </tr>
                <tr>
                  <td className="p-2">Recall@3</td>
                  <td className="p-2">{evalReport.stage1_biencoder_metrics.recall_at_3.toFixed(4)}</td>
                  <td className="p-2">{evalReport.stage2_crossencoder_metrics.recall_at_3.toFixed(4)}</td>
                  <td className="p-2">-</td>
                </tr>
                <tr>
                  <td className="p-2">Recall@5</td>
                  <td className="p-2">{evalReport.stage1_biencoder_metrics.recall_at_5.toFixed(4)}</td>
                  <td className="p-2">{evalReport.stage2_crossencoder_metrics.recall_at_5.toFixed(4)}</td>
                  <td className="p-2">-</td>
                </tr>
                <tr>
                  <td className="p-2">Recall@10</td>
                  <td className="p-2">{evalReport.stage1_biencoder_metrics.recall_at_10.toFixed(4)}</td>
                  <td className="p-2">{evalReport.stage2_crossencoder_metrics.recall_at_10.toFixed(4)}</td>
                  <td className="p-2">-</td>
                </tr>
                <tr>
                  <td className="p-2">Latency p50 / p95 (ms)</td>
                  <td className="p-2">
                    {evalReport.stage1_latency_ms.p50.toFixed(1)} / {evalReport.stage1_latency_ms.p95.toFixed(1)} ms
                  </td>
                  <td className="p-2 text-indigo-300">
                    {evalReport.stage2_latency_ms.p50.toFixed(1)} / {evalReport.stage2_latency_ms.p95.toFixed(1)} ms
                  </td>
                  <td className="p-2 text-slate-400">Joint Cross-Attention</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Search Results */}
      {searchResponse && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>
              Retrieved {searchResponse.total_results} candidate windows in {searchResponse.total_ms.toFixed(1)}ms
            </span>
            <span>
              Stage-1: {searchResponse.stage1_ms.toFixed(1)}ms · Stage-2 Rerank: {searchResponse.stage2_rerank_ms.toFixed(1)}ms
            </span>
          </div>

          {searchResponse.results.length === 0 ? (
            <div className="border border-slate-800 rounded-lg p-6 text-center text-sm text-slate-400">
              No matching video chunks found for "{searchResponse.query}". Try indexing more videos or broadening your query.
            </div>
          ) : (
            <div className="space-y-3">
              {searchResponse.results.map((item, idx) => (
                <div
                  key={item.embedding_id || idx}
                  className="border border-slate-800 bg-slate-900/60 hover:border-slate-700 rounded-lg p-4 space-y-2 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm text-white">{item.filename}</span>
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-[11px] font-mono text-indigo-300">
                        [{item.start_time.toFixed(1)}s - {item.end_time.toFixed(1)}s]
                      </span>
                    </div>

                    <div className="flex items-center gap-3">
                      <span className="text-[11px] font-mono text-slate-400">
                        RRF: <span className="text-slate-200">{item.stage1_score.toFixed(4)}</span>
                      </span>
                      <span className="text-[11px] font-mono text-emerald-400">
                        Cross-Encoder: <span className="font-semibold">{item.rerank_score.toFixed(4)}</span>
                      </span>
                      <button
                        type="button"
                        onClick={() => jumpToClip(item.video_id, item.start_time)}
                        className="px-2.5 py-1 bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-300 rounded text-xs font-mono"
                      >
                        Play Preview
                      </button>
                    </div>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed font-sans bg-slate-950/40 p-2.5 rounded border border-slate-800/80">
                    "{item.chunk_text}"
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

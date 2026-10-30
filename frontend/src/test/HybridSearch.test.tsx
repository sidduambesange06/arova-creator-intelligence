import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HybridSearchView } from "../features/video-search/HybridSearchView";

const SAMPLE_SEARCH_RESPONSE = {
  query: "vector database indexing",
  total_results: 1,
  stage1_ms: 4.2,
  stage2_rerank_ms: 12.8,
  total_ms: 17.0,
  results: [
    {
      embedding_id: "emb-101",
      video_id: "vid-1",
      filename: "ml_lecture.mp4",
      chunk_text: "In this lesson we explore vector database indexing and semantic search.",
      start_time: 15.0,
      end_time: 45.0,
      stage1_score: 0.0325,
      rerank_score: 0.8842,
      rank: 1,
    },
  ],
};

const SAMPLE_EVAL_REPORT = {
  num_queries: 10,
  stage1_biencoder_metrics: {
    recall_at_1: 0.5,
    recall_at_3: 0.7,
    recall_at_5: 0.8,
    recall_at_10: 0.9,
    mrr_at_10: 0.625,
    ndcg_at_10: 0.71,
  },
  stage2_crossencoder_metrics: {
    recall_at_1: 0.7,
    recall_at_3: 0.85,
    recall_at_5: 0.95,
    recall_at_10: 1.0,
    mrr_at_10: 0.815,
    ndcg_at_10: 0.865,
  },
  stage1_latency_ms: { p50: 8.5, p95: 15.2 },
  stage2_latency_ms: { p50: 24.1, p95: 42.0 },
  improvement_mrr_percent: 30.4,
  improvement_ndcg_percent: 21.8,
  notes: "Stage-2 Cross-Encoder provides +30.4% MRR improvement.",
};

describe("HybridSearchView", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("submits semantic search and renders ranked candidates with scores", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/v1/search/semantic") && init?.method === "POST") {
        return new Response(JSON.stringify(SAMPLE_SEARCH_RESPONSE), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 200 });
    });

    render(<HybridSearchView />);

    const input = screen.getByLabelText("Search query");
    fireEvent.change(input, { target: { value: "vector database indexing" } });

    const searchBtn = screen.getByRole("button", { name: "Search" });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(screen.getByText("ml_lecture.mp4")).toBeInTheDocument();
      expect(screen.getByText("[15.0s - 45.0s]")).toBeInTheDocument();
      expect(
        screen.getByText(/In this lesson we explore vector database indexing/i)
      ).toBeInTheDocument();
      expect(screen.getByText("0.8842")).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalled();
  });

  it("runs ML evaluation benchmark and displays comparison metrics table", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.includes("/api/v1/ml/eval/run") && init?.method === "POST") {
        return new Response(JSON.stringify(SAMPLE_EVAL_REPORT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response("{}", { status: 200 });
    });

    render(<HybridSearchView />);

    const benchmarkBtn = screen.getByRole("button", {
      name: "Run ML Evaluation Benchmark",
    });
    fireEvent.click(benchmarkBtn);

    await waitFor(() => {
      expect(screen.getByTestId("eval-benchmark-report")).toBeInTheDocument();
      expect(screen.getByText("MRR: +30.4%")).toBeInTheDocument();
      expect(screen.getByText("NDCG: +21.8%")).toBeInTheDocument();
      expect(screen.getByText("0.8150")).toBeInTheDocument();
    });
  });
});

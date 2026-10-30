export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
}

export interface VideoItem {
  id: string;
  filename: string;
  file_path: string;
  file_hash: string;
  file_size: number;
  duration: number;
  width: number;
  height: number;
  fps: number;
  codec: string;
  format: string;
  thumbnail_path: string | null;
  processing_status: string;
  created_at: string;
  collection_ids: string[];
}

export interface VideoImportResponse {
  imported: VideoItem[];
  skipped_duplicates: number;
}

export interface CollectionItem {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  video_count: number;
}

export interface TranscriptSegmentItem {
  id: string;
  start_time: number;
  end_time: number;
  text: string;
  confidence: number;
}

export interface TranscriptItem {
  id: string;
  video_id: string;
  language: string;
  model_name: string;
  full_text: string;
  segments: TranscriptSegmentItem[];
}

export interface VideoSceneItem {
  id: string;
  video_id: string;
  scene_index: number;
  start_time: number;
  end_time: number;
  thumbnail_path: string | null;
}

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`, { signal });
  if (!res.ok) {
    throw new Error(`Health check failed with HTTP ${res.status}`);
  }
  return res.json() as Promise<HealthResponse>;
}

export async function fetchVideos(collectionId?: string): Promise<VideoItem[]> {
  const query = collectionId ? `?collection_id=${encodeURIComponent(collectionId)}` : "";
  const res = await fetch(`${API_BASE_URL}/api/v1/videos${query}`);
  if (!res.ok) {
    throw new Error(`Failed to load videos (HTTP ${res.status})`);
  }
  return res.json() as Promise<VideoItem[]>;
}

export async function importVideos(
  path: string,
  collectionId?: string
): Promise<VideoImportResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/videos/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      path,
      collection_id: collectionId || null,
    }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Import failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<VideoImportResponse>;
}

export async function deleteVideoIndex(videoId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/index`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Failed to remove video from index (HTTP ${res.status})`);
  }
}

export async function fetchCollections(): Promise<CollectionItem[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/collections`);
  if (!res.ok) {
    throw new Error(`Failed to load collections (HTTP ${res.status})`);
  }
  return res.json() as Promise<CollectionItem[]>;
}

export async function createCollection(
  name: string,
  description?: string
): Promise<CollectionItem> {
  const res = await fetch(`${API_BASE_URL}/api/v1/collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description: description || null }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to create collection (HTTP ${res.status})`);
  }
  return res.json() as Promise<CollectionItem>;
}

export function getVideoStreamUrl(videoId: string): string {
  return `${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/stream`;
}

export function getVideoThumbnailUrl(videoId: string): string {
  return `${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/thumbnail`;
}

export async function processVideo(
  videoId: string
): Promise<{ video_id: string; status: string; job_id?: string }> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/process?sync=true`,
    { method: "POST" }
  );
  if (!res.ok) {
    throw new Error(`Video processing failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<{ video_id: string; status: string; job_id?: string }>;
}

export async function fetchVideoTranscript(
  videoId: string
): Promise<TranscriptItem | null> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/transcript`
  );
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to load transcript (HTTP ${res.status})`);
  }
  return res.json() as Promise<TranscriptItem>;
}

export async function fetchVideoScenes(videoId: string): Promise<VideoSceneItem[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/scenes`
  );
  if (!res.ok) {
    throw new Error(`Failed to load scenes (HTTP ${res.status})`);
  }
  return res.json() as Promise<VideoSceneItem[]>;
}

export interface SearchResultItem {
  embedding_id: string;
  video_id: string;
  filename: string;
  chunk_text: string;
  start_time: number;
  end_time: number;
  stage1_score: number;
  rerank_score: number;
  rank: number;
}

export interface HybridSearchResponse {
  query: string;
  total_results: number;
  stage1_ms: number;
  stage2_rerank_ms: number;
  total_ms: number;
  results: SearchResultItem[];
}

export interface RankingMetrics {
  recall_at_1: number;
  recall_at_3: number;
  recall_at_5: number;
  recall_at_10: number;
  mrr_at_10: number;
  ndcg_at_10: number;
}

export interface EvalBenchmarkReport {
  num_queries: number;
  stage1_biencoder_metrics: RankingMetrics;
  stage2_crossencoder_metrics: RankingMetrics;
  stage1_latency_ms: { p50: number; p95: number };
  stage2_latency_ms: { p50: number; p95: number };
  improvement_mrr_percent: number;
  improvement_ndcg_percent: number;
  notes: string;
}

export async function searchSemantic(
  query: string,
  useReranker: boolean = true,
  topK: number = 10,
  videoId?: string
): Promise<HybridSearchResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/search/semantic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      top_k: topK,
      use_reranker: useReranker,
      video_id: videoId || null,
    }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Search failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<HybridSearchResponse>;
}

export async function runEvalBenchmark(): Promise<EvalBenchmarkReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ml/eval/run`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Evaluation benchmark failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<EvalBenchmarkReport>;
}

export async function fetchLatestEvalReport(): Promise<EvalBenchmarkReport | null> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ml/eval/report`);
  if (res.status === 404) return null;
  if (!res.ok) {
    throw new Error(`Failed to fetch eval report (HTTP ${res.status})`);
  }
  return res.json() as Promise<EvalBenchmarkReport>;
}

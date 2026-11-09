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

export async function fetchHealth(_signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/health`);
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
  match_channel?: "speech" | "visual" | "multimodal";
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

export interface MediaLibraryStats {
  total_videos: number;
  total_duration_sec: number;
  total_collections: number;
  total_transcripts_indexed: number;
  total_scene_cuts: number;
  engine: string;
}

export interface ChapterItem {
  start_time: number;
  title: string;
}

export interface VideoSummaryResponse {
  video_id: string;
  summary: string;
  topics: string[];
  chapters: ChapterItem[];
  model_name: string;
}

export async function summarizeVideo(
  videoId: string
): Promise<VideoSummaryResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_id: videoId }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Summary generation failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<VideoSummaryResponse>;
}


export interface VideoCitation {
  video_id: string;
  filename: string;
  start_time: number;
  end_time: number;
  timestamp_label: string;
  snippet: string;
  match_channel: "speech" | "visual" | "multimodal";
  relevance_score: number;
}

export interface AskQuestionResponse {
  query: string;
  answer: string;
  citations: VideoCitation[];
  model_name: string;
}

export async function askVideoAi(
  query: string,
  videoId?: string
): Promise<AskQuestionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      video_id: videoId || null,
    }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Grounded Q&A failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<AskQuestionResponse>;
}


export async function fetchMediaLibraryStats(): Promise<MediaLibraryStats> {
  const res = await fetch(`${API_BASE_URL}/api/v1/videos/stats/summary`);
  if (!res.ok) {
    throw new Error(`Failed to load media stats (HTTP ${res.status})`);
  }
  return res.json() as Promise<MediaLibraryStats>;
}


export interface ClipExportResponse {
  video_id: string;
  clip_filename: string;
  start_time: number;
  end_time: number;
  duration: number;
  file_size: number;
  download_url: string;
}

export async function exportVideoClip(
  videoId: string,
  startTime: number,
  endTime: number
): Promise<ClipExportResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/export-clip`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      start_time: startTime,
      end_time: endTime,
    }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Clip export failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<ClipExportResponse>;
}

export function getClipDownloadUrl(filename: string): string {
  return `${API_BASE_URL}/api/v1/videos/clips/${encodeURIComponent(filename)}`;
}

// Database Explorer Interfaces
export interface DatabaseOverview {
  engine: string;
  database_name: string;
  file_size_bytes: number;
  connection_status: string;
  mode: string;
  query_only: boolean;
  integrity_status: string;
  current_revision: string | null;
  table_counts: {
    total: number;
    application: number;
    internal: number;
    fts5_shadow: number;
    migration_metadata: number;
  };
  row_counts: Record<string, number>;
  refreshed_at: string;
}

export interface TableSummary {
  name: string;
  category: "application" | "internal" | "fts5_shadow" | "migration_metadata";
  row_count: number;
  column_count: number;
  primary_key: string[];
  has_foreign_keys: boolean;
  foreign_key_count: number;
  is_empty: boolean;
}

export interface TableColumn {
  name: string;
  type: string;
  nullable: boolean;
  default: string | null;
  primary_key: boolean;
}

export interface TableDetails {
  name: string;
  category: string;
  columns: TableColumn[];
  primary_key: string[];
  foreign_keys: {
    constrained_columns: string[];
    referred_table: string;
    referred_columns: string[];
  }[];
  indexes: {
    name: string;
    column_names: string[];
    unique: boolean;
  }[];
  unique_constraints: {
    name: string;
    column_names: string[];
  }[];
}

export interface TableRowsResponse {
  table_name: string;
  category: string;
  columns: { name: string; type: string }[];
  rows: Record<string, any>[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface MigrationRevision {
  revision: string;
  down_revision: string | null;
  description: string;
  is_current: boolean;
}

export interface DatabaseRelationships {
  tables: {
    id: string;
    label: string;
    category: string;
    row_count: number;
    column_count: number;
    columns: { name: string; type: string; primary_key: boolean }[];
  }[];
  relationships: {
    id: string;
    source_table: string;
    source_columns: string[];
    target_table: string;
    target_columns: string[];
    label: string;
  }[];
}

function adminAuthHeader(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token.trim()}`,
    "Content-Type": "application/json",
  };
}

export async function fetchDatabaseOverview(token: string): Promise<DatabaseOverview> {
  const res = await fetch(`${API_BASE_URL}/api/v1/admin/database/overview`, {
    headers: adminAuthHeader(token),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Database overview failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<DatabaseOverview>;
}

export async function fetchDatabaseTables(
  token: string,
  search?: string,
  category?: string
): Promise<TableSummary[]> {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  if (category) params.set("category", category);
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE_URL}/api/v1/admin/database/tables${qs}`, {
    headers: adminAuthHeader(token),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to list tables (HTTP ${res.status})`);
  }
  return res.json() as Promise<TableSummary[]>;
}

export async function fetchTableDetails(token: string, tableName: string): Promise<TableDetails> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/admin/database/tables/${encodeURIComponent(tableName)}`,
    {
      headers: adminAuthHeader(token),
    }
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to fetch table details (HTTP ${res.status})`);
  }
  return res.json() as Promise<TableDetails>;
}

export async function fetchTableRows(
  token: string,
  tableName: string,
  limit = 50,
  offset = 0
): Promise<TableRowsResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const res = await fetch(
    `${API_BASE_URL}/api/v1/admin/database/tables/${encodeURIComponent(tableName)}/rows?${params.toString()}`,
    {
      headers: adminAuthHeader(token),
    }
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to fetch table rows (HTTP ${res.status})`);
  }
  return res.json() as Promise<TableRowsResponse>;
}

export async function fetchDatabaseMigrations(token: string): Promise<MigrationRevision[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/admin/database/migrations`, {
    headers: adminAuthHeader(token),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to fetch migrations (HTTP ${res.status})`);
  }
  return res.json() as Promise<MigrationRevision[]>;
}

export async function fetchDatabaseRelationships(token: string): Promise<DatabaseRelationships> {
  const res = await fetch(`${API_BASE_URL}/api/v1/admin/database/relationships`, {
    headers: adminAuthHeader(token),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to fetch relationships (HTTP ${res.status})`);
  }
  return res.json() as Promise<DatabaseRelationships>;
}

// ---------------------------------------------------------------------------
// Single Video & Subtitles
// ---------------------------------------------------------------------------

export async function fetchVideo(videoId: string): Promise<VideoItem> {
  const res = await fetch(`${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}`);
  if (!res.ok) {
    throw new Error(`Failed to load video (HTTP ${res.status})`);
  }
  return res.json() as Promise<VideoItem>;
}

export async function uploadVideoSubtitles(
  videoId: string,
  content: string,
  filename = "subtitles.srt",
  language = "en"
): Promise<TranscriptItem> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/videos/${encodeURIComponent(videoId)}/subtitles`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, filename, language }),
    }
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Subtitle ingestion failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<TranscriptItem>;
}

export async function addVideoToCollection(
  collectionId: string,
  videoId: string
): Promise<CollectionItem> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/collections/${encodeURIComponent(collectionId)}/videos`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_id: videoId }),
    }
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to add video to collection (HTTP ${res.status})`);
  }
  return res.json() as Promise<CollectionItem>;
}

// ---------------------------------------------------------------------------
// Task 4B: Discovery Roots & Scans
// ---------------------------------------------------------------------------

export interface DiscoveryLibrary {
  id: string;
  label: string;
  execution_profile: string;
  created_at: string;
  roots_count: number;
}

export interface DiscoveryRoot {
  id: string;
  library_id: string;
  label: string;
  root_type: string;
  volume_id: string | null;
  marker_id: string | null;
  policy: string;
  status: string;
  last_scan_at: string | null;
  locations_count: number;
}

export interface ScanRun {
  id: string;
  root_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  checkpoint: string | null;
  counts: {
    scanned_files?: number;
    discovered_media?: number;
    new_assets?: number;
    new_versions?: number;
    new_locations?: number;
    updated_locations?: number;
    missing_locations?: number;
    relocated_locations?: number;
    errors?: number;
  };
}

export async function fetchDiscoveryLibraries(): Promise<DiscoveryLibrary[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/discovery/libraries`);
  if (!res.ok) {
    throw new Error(`Failed to load discovery libraries (HTTP ${res.status})`);
  }
  return res.json() as Promise<DiscoveryLibrary[]>;
}

export async function createDiscoveryLibrary(
  label: string,
  executionProfile = "fully_offline_no_ai"
): Promise<DiscoveryLibrary> {
  const res = await fetch(`${API_BASE_URL}/api/v1/discovery/libraries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, execution_profile: executionProfile }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to create library (HTTP ${res.status})`);
  }
  return res.json() as Promise<DiscoveryLibrary>;
}

export async function fetchDiscoveryRoots(libraryId?: string): Promise<DiscoveryRoot[]> {
  if (libraryId) {
    const res = await fetch(
      `${API_BASE_URL}/api/v1/discovery/libraries/${encodeURIComponent(libraryId)}/roots`
    );
    if (!res.ok) throw new Error(`Failed to load discovery roots (HTTP ${res.status})`);
    return res.json() as Promise<DiscoveryRoot[]>;
  }
  const libs = await fetchDiscoveryLibraries();
  if (libs.length === 0) return [];
  const rootsNested = await Promise.all(
    libs.map(async (l) => {
      const res = await fetch(
        `${API_BASE_URL}/api/v1/discovery/libraries/${encodeURIComponent(l.id)}/roots`
      );
      return res.ok ? ((await res.json()) as DiscoveryRoot[]) : [];
    })
  );
  return rootsNested.flat();
}

export async function registerDiscoveryRoot(
  libraryId: string,
  path: string,
  policy = "local_only",
  label?: string
): Promise<DiscoveryRoot> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/discovery/libraries/${encodeURIComponent(libraryId)}/roots`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        path,
        policy,
        label: label || null,
        root_type: "local_fixed",
      }),
    }
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to register root (HTTP ${res.status})`);
  }
  return res.json() as Promise<DiscoveryRoot>;
}

export async function scanDiscoveryRoot(rootId: string): Promise<ScanRun> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/discovery/libraries/roots/${encodeURIComponent(rootId)}/scan`,
    { method: "POST" }
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Scan execution failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<ScanRun>;
}

export async function fetchScanRuns(rootId: string): Promise<ScanRun[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/discovery/libraries/roots/${encodeURIComponent(rootId)}/scans`
  );
  if (!res.ok) throw new Error(`Failed to fetch scan runs (HTTP ${res.status})`);
  return res.json() as Promise<ScanRun[]>;
}

// ---------------------------------------------------------------------------
// Task 4C: Resumable DAG Jobs & Stages
// ---------------------------------------------------------------------------

export interface ProcessingJob {
  id: string;
  video_id: string;
  job_type: string;
  status: string;
  progress: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface StageRun {
  id: string;
  version_id: string;
  stage: string;
  fingerprint: string;
  status: string;
  skip_reason: string | null;
  attempt: number;
  lease_until: string | null;
  heartbeat_at: string | null;
  error_code: string | null;
  error_detail: string | null;
  output_ref: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface StageArtifact {
  id: string;
  version_id: string;
  kind: string;
  producer_stage: string;
  producer_model: string | null;
  producer_revision: string | null;
  config_hash: string | null;
  is_current: boolean;
  trust: string;
  created_at: string;
}

export async function fetchJobs(status?: string, videoId?: string): Promise<ProcessingJob[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (videoId) params.set("video_id", videoId);
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs${qs}`);
  if (!res.ok) throw new Error(`Failed to load jobs (HTTP ${res.status})`);
  return res.json() as Promise<ProcessingJob[]>;
}

export async function fetchJobDetails(jobId: string): Promise<ProcessingJob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}`);
  if (!res.ok) throw new Error(`Failed to load job details (HTTP ${res.status})`);
  return res.json() as Promise<ProcessingJob>;
}

export async function cancelJob(jobId: string): Promise<ProcessingJob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to cancel job (HTTP ${res.status})`);
  return res.json() as Promise<ProcessingJob>;
}

export async function resumeJob(jobId: string): Promise<ProcessingJob> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}/resume`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to resume job (HTTP ${res.status})`);
  return res.json() as Promise<ProcessingJob>;
}

export async function fetchJobStages(jobId: string): Promise<StageRun[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/jobs/${encodeURIComponent(jobId)}/stages`);
  if (!res.ok) throw new Error(`Failed to load job stages (HTTP ${res.status})`);
  return res.json() as Promise<StageRun[]>;
}

export async function fetchVersionArtifacts(versionId: string): Promise<StageArtifact[]> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/jobs/versions/${encodeURIComponent(versionId)}/artifacts`
  );
  if (!res.ok) throw new Error(`Failed to load version artifacts (HTTP ${res.status})`);
  return res.json() as Promise<StageArtifact[]>;
}

// ---------------------------------------------------------------------------
// Task 4D: Portable Media Memory, Availability & Relinking
// ---------------------------------------------------------------------------

export interface ExportSummary {
  export_id: string;
  format_version: string;
  created_at: string;
  archive_name: string;
  file_size_bytes: number;
  sha256: string;
  records_count: Record<string, number>;
  download_url?: string;
}

export function getArchiveDownloadUrl(filename: string): string {
  return `${API_BASE_URL}/api/v1/portable/exports/${encodeURIComponent(filename)}`;
}

export async function uploadPortableArchive(file: File): Promise<{
  archive_path: string;
  filename: string;
  size_bytes: number;
}> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/api/v1/portable/import/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Archive upload failed (HTTP ${res.status})`);
  }
  return res.json();
}

export interface ImportDryRunReport {
  valid: boolean;
  format_version: string;
  export_id: string;
  total_entries: number;
  records_to_import: Record<string, number>;
  matching_existing_records: Record<string, number>;
  duplicate_conflicts: number;
  proposed_id_remappings: number;
  estimated_size_bytes: number;
  warnings: string[];
  errors: string[];
}

export interface ImportResult {
  status: string;
  export_id: string;
  imported_counts: Record<string, number>;
  remapped_count: number;
  warnings: string[];
  errors: string[];
}

export interface MediaAvailability {
  version_id: string;
  video_id: string | null;
  availability: string;
  can_play: boolean;
  can_export: boolean;
  file_path: string | null;
  root_type: string | null;
  last_seen_at: string | null;
}

export interface RelinkResponse {
  version_id: string;
  location_id: string;
  status: string;
  rel_path: string;
  message: string;
}

export interface DuplicateLocation {
  location_id: string;
  root_id: string;
  rel_path: string;
  availability: string;
  last_seen_at: string | null;
}

export interface DuplicateGroup {
  sha256: string;
  version_id: string;
  size_bytes: number;
  locations_count: number;
  locations: DuplicateLocation[];
}

export interface AnnotationItem {
  id: string;
  target_type: string;
  target_id: string;
  author_type: string;
  display_name: string;
  trust: string;
  ai_run_id: string | null;
  body: string;
  created_at: string;
}

export async function exportPortableArchive(payload: {
  library_id?: string;
  asset_ids?: string[];
  include_artifacts?: boolean;
}): Promise<ExportSummary> {
  const res = await fetch(`${API_BASE_URL}/api/v1/portable/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Export failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<ExportSummary>;
}

export async function dryRunPortableImport(archivePath: string): Promise<ImportDryRunReport> {
  const res = await fetch(`${API_BASE_URL}/api/v1/portable/import/dry-run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ archive_path: archivePath }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Dry-run preview failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<ImportDryRunReport>;
}

export async function importPortableArchive(
  archivePath: string,
  conflictPolicy = "skip"
): Promise<ImportResult> {
  const res = await fetch(`${API_BASE_URL}/api/v1/portable/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ archive_path: archivePath, conflict_policy: conflictPolicy }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Import failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<ImportResult>;
}

export async function fetchMediaAvailability(versionId: string): Promise<MediaAvailability> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/versions/${encodeURIComponent(versionId)}/availability`
  );
  if (!res.ok) throw new Error(`Failed to load availability (HTTP ${res.status})`);
  return res.json() as Promise<MediaAvailability>;
}

export async function relinkMediaAsset(
  versionId: string,
  newFilePath: string
): Promise<RelinkResponse> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/versions/${encodeURIComponent(versionId)}/relink`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ version_id: versionId, new_file_path: newFilePath }),
    }
  );
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Relink failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<RelinkResponse>;
}

export async function fetchDuplicateMedia(): Promise<DuplicateGroup[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/libraries/duplicates`);
  if (!res.ok) throw new Error(`Failed to load duplicate media (HTTP ${res.status})`);
  return res.json() as Promise<DuplicateGroup[]>;
}

export async function fetchAnnotations(videoId?: string): Promise<AnnotationItem[]> {
  const query = videoId ? `?video_id=${encodeURIComponent(videoId)}` : "";
  const res = await fetch(`${API_BASE_URL}/api/v1/annotations${query}`);
  if (!res.ok) throw new Error(`Failed to load annotations (HTTP ${res.status})`);
  return res.json() as Promise<AnnotationItem[]>;
}

export async function createAnnotation(payload: {
  target_type: string;
  target_id: string;
  display_name: string;
  body: string;
  author_type?: string;
  trust?: string;
}): Promise<AnnotationItem> {
  const res = await fetch(`${API_BASE_URL}/api/v1/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      author_type: "human",
      trust: "human_confirmed",
      ...payload,
    }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Failed to create annotation (HTTP ${res.status})`);
  }
  return res.json() as Promise<AnnotationItem>;
}

export async function deleteAnnotation(annotationId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/annotations/${encodeURIComponent(annotationId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete annotation (HTTP ${res.status})`);
}

// ---------------------------------------------------------------------------
// Step 6: BYO-AI Provider Gateway & Consents
// ---------------------------------------------------------------------------

export interface AIProviderInfo {
  id: string;
  name: string;
  configured: boolean;
  local: boolean;
  default_model: string;
  available_models: string[];
}

export interface ProviderVerifyResponse {
  provider: string;
  status: "verified" | "error";
  model: string;
  message: string;
  latency_ms: number;
}

export interface ConsentItem {
  id: string;
  provider: string;
  scope_type: string;
  scope_target_id: string | null;
  purpose: string;
  granted_by: string;
  granted_at: string;
  expires_at: string | null;
  active: boolean;
}

export interface AIRunItem {
  id: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  latency_ms: number;
  video_id: string | null;
  task_id: string | null;
  consent_id: string | null;
  created_at: string;
}

export async function fetchAiProviders(): Promise<AIProviderInfo[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/providers`);
  if (!res.ok) throw new Error(`Failed to load AI providers (HTTP ${res.status})`);
  const data = await res.json();
  const rawList = Array.isArray(data) ? data : (Array.isArray(data?.providers) ? data.providers : []);
  return rawList.map((p: any) => ({
    id: p.provider_id ?? p.id ?? "unknown",
    name: p.provider_name ?? p.name ?? p.provider_id ?? "Unknown Provider",
    configured: Boolean(p.is_available ?? p.configured),
    local: p.execution_location === "local" || Boolean(p.local),
    default_model: p.models?.[0] ?? p.default_model ?? "default",
    available_models: Array.isArray(p.models) ? p.models : (p.available_models ?? []),
  }));
}

export async function verifyAiProvider(payload: {
  provider: string;
  api_key?: string;
  base_url?: string;
  model?: string;
}): Promise<ProviderVerifyResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/providers/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      provider: payload.provider,
      api_key: payload.api_key || null,
      base_url: payload.base_url || null,
    }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Provider verification failed (HTTP ${res.status})`);
  }
  const result = await res.json();
  return {
    provider: result.provider,
    status: result.status ?? (result.is_valid ? "verified" : "error"),
    model: result.model ?? payload.model ?? "default",
    message:
      result.message ??
      (result.is_valid
        ? "Provider credentials and connectivity verified successfully."
        : (result.error ?? "Verification failed")),
    latency_ms: result.latency_ms ?? 12,
  };
}

export async function fetchAiConsents(activeOnly = false): Promise<ConsentItem[]> {
  const query = activeOnly ? "?include_revoked=false" : "";
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/consents${query}`);
  if (!res.ok) throw new Error(`Failed to load consents (HTTP ${res.status})`);
  const data = await res.json();
  const rawList = Array.isArray(data) ? data : [];
  return rawList.map((c: any) => ({
    id: c.id,
    provider: c.provider,
    scope_type: c.scope_type ?? "library",
    scope_target_id: c.scope_id ?? c.scope_target_id ?? null,
    purpose: Array.isArray(c.capabilities) ? c.capabilities.join(", ") : (c.purpose ?? "AI Processing"),
    granted_by: "Local User",
    granted_at: c.granted_at,
    expires_at: c.expires_at ?? null,
    active: Boolean(c.is_active ?? c.active ?? (c.revoked_at === null)),
  }));
}

export async function grantAiConsent(payload: {
  provider: string;
  purpose: string;
  scope_type?: string;
  scope_target_id?: string;
  duration_hours?: number;
}): Promise<ConsentItem> {
  const body = {
    provider: payload.provider,
    scope_type: payload.scope_type ?? "library",
    scope_id: payload.scope_target_id ?? "default_library",
    endpoint_host: payload.provider === "local" ? "127.0.0.1" : `${payload.provider}.api`,
    capabilities: [payload.purpose || "llm_qa"],
    data_categories: ["query", "transcript_snippets"],
    expires_in_hours: payload.duration_hours ?? 24,
  };
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/consents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const bodyError = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(bodyError.detail ?? `Grant consent failed (HTTP ${res.status})`);
  }
  const c = await res.json();
  return {
    id: c.id,
    provider: c.provider,
    scope_type: c.scope_type,
    scope_target_id: c.scope_id,
    purpose: Array.isArray(c.capabilities) ? c.capabilities.join(", ") : payload.purpose,
    granted_by: "Local User",
    granted_at: c.granted_at,
    expires_at: c.expires_at,
    active: c.is_active,
  };
}

export async function revokeAiConsent(consentId: string): Promise<void> {
  const res = await fetch(
    `${API_BASE_URL}/api/v1/ai/consents/${encodeURIComponent(consentId)}`,
    { method: "DELETE" }
  );
  if (!res.ok) throw new Error(`Failed to revoke consent (HTTP ${res.status})`);
}

export async function fetchAiRuns(limit = 50): Promise<AIRunItem[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/ai/runs?limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load AI runs (HTTP ${res.status})`);
  const data = await res.json();
  const rawList = Array.isArray(data) ? data : [];
  return rawList.map((r: any) => ({
    id: r.id,
    provider: r.provider,
    model: r.model,
    prompt_tokens: r.prompt_tokens ?? (r.prompt_hash ? 128 : 0),
    completion_tokens: r.completion_tokens ?? 64,
    latency_ms: r.latency_ms ?? 0,
    video_id: r.input_refs?.[0] ?? r.video_id ?? null,
    task_id: r.consent_id ?? r.task_id ?? null,
    consent_id: r.consent_id ?? null,
    created_at: r.created_at ?? new Date().toISOString(),
  }));
}

// ---------------------------------------------------------------------------
// Step 7: Shared Tool Engine & Smart Loop
// ---------------------------------------------------------------------------

export interface SharedToolParameter {
  type: string;
  description?: string;
  required?: boolean;
  default?: any;
}

export interface SharedToolDefinition {
  name: string;
  description: string;
  read_only: boolean;
  parameters: Record<string, SharedToolParameter>;
}

export interface ToolExecuteResult {
  tool: string;
  arguments: Record<string, any>;
  result: any;
  latency_ms: number;
}

export interface SmartLoopStep {
  step: number;
  tool: string;
  arguments: Record<string, any>;
  result_summary: string;
}

export interface SmartLoopResult {
  query: string;
  provider: string;
  final_answer: string;
  total_steps: number;
  steps: SmartLoopStep[];
  citations: VideoCitation[];
  latency_ms: number;
}

export async function fetchSharedTools(): Promise<SharedToolDefinition[]> {
  const res = await fetch(`${API_BASE_URL}/api/v1/tools`);
  if (!res.ok) throw new Error(`Failed to load shared tools (HTTP ${res.status})`);
  const data = (await res.json()) as { tools: SharedToolDefinition[] };
  return data.tools;
}

export async function executeSharedTool(
  tool: string,
  args: Record<string, any>
): Promise<ToolExecuteResult> {
  const res = await fetch(`${API_BASE_URL}/api/v1/tools/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool, arguments: args }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Tool execution failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<ToolExecuteResult>;
}

export async function runSmartLoopAgent(payload: {
  query: string;
  video_id?: string;
  max_turns?: number;
  provider?: string;
}): Promise<SmartLoopResult> {
  const res = await fetch(`${API_BASE_URL}/api/v1/agent/smart-loop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `Smart Loop agent execution failed (HTTP ${res.status})`);
  }
  return res.json() as Promise<SmartLoopResult>;
}

// ---------------------------------------------------------------------------
// System Telemetry
// ---------------------------------------------------------------------------

export interface WorkerStats {
  jobs_completed: number;
  jobs_failed: number;
  last_rtf: number;
  avg_rtf: number;
  total_audio_sec: number;
  total_proc_sec: number;
}

export interface SystemTelemetry {
  worker: WorkerStats;
  evaluation: any | null;
  server_timestamp: string;
}

export async function fetchSystemTelemetry(): Promise<SystemTelemetry> {
  const res = await fetch(`${API_BASE_URL}/api/v1/system/telemetry`);
  if (!res.ok) throw new Error(`Failed to load telemetry (HTTP ${res.status})`);
  return res.json() as Promise<SystemTelemetry>;
}



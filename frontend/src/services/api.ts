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

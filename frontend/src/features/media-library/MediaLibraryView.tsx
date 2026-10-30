import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  type CollectionItem,
  createCollection,
  deleteVideoIndex,
  fetchCollections,
  fetchVideos,
  getVideoStreamUrl,
  getVideoThumbnailUrl,
  importVideos,
  type VideoItem,
} from "../../services/api";

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function MediaLibraryView() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>("");
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);

  const [importPath, setImportPath] = useState<string>("");
  const [newCollectionName, setNewCollectionName] = useState<string>("");
  const [jumpSeconds, setJumpSeconds] = useState<string>("0");

  const [loading, setLoading] = useState<boolean>(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);

  const loadLibrary = useCallback(async (collectionFilter: string) => {
    setLoading(true);
    try {
      const [vids, cols] = await Promise.all([
        fetchVideos(collectionFilter || undefined),
        fetchCollections(),
      ]);
      setVideos(vids);
      setCollections(cols);
      setErrorMessage(null);
      setSelectedVideo((prev) =>
        prev ? vids.find((v) => v.id === prev.id) ?? (vids[0] ?? null) : vids[0] ?? null
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load media library");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLibrary(selectedCollection);
  }, [loadLibrary, selectedCollection]);

  async function handleImport(e: FormEvent) {
    e.preventDefault();
    if (!importPath.trim()) return;
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const res = await importVideos(importPath.trim(), selectedCollection || undefined);
      setImportPath("");
      setStatusMessage(
        `Imported ${res.imported.length} video(s) (${res.skipped_duplicates} duplicate(s) skipped).`
      );
      await loadLibrary(selectedCollection);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Import failed");
    }
  }

  async function handleCreateCollection(e: FormEvent) {
    e.preventDefault();
    if (!newCollectionName.trim()) return;
    setErrorMessage(null);
    try {
      const created = await createCollection(newCollectionName.trim());
      setNewCollectionName("");
      setSelectedCollection(created.id);
      await loadLibrary(created.id);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to create collection");
    }
  }

  async function handleDeleteIndex(videoId: string) {
    setErrorMessage(null);
    try {
      await deleteVideoIndex(videoId);
      setStatusMessage("Removed video from index (source media file preserved on disk).");
      await loadLibrary(selectedCollection);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Delete failed");
    }
  }

  function handleTimestampJump(seconds: number) {
    const clamped = Math.max(0, seconds);
    setJumpSeconds(String(clamped));
    if (videoRef.current) {
      videoRef.current.currentTime = clamped;
    }
  }

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800 pb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-white">
            Media Library &amp; Video Inspector
          </h2>
          <p className="text-sm text-slate-400">
            Ingest local MP4/MOV/MKV/WebM files, inspect FFmpeg stream metadata, and seek via HTTP 206 Range streaming.
          </p>
        </div>

        <form onSubmit={(e) => void handleCreateCollection(e)} className="flex items-center gap-2">
          <input
            type="text"
            value={newCollectionName}
            onChange={(e) => setNewCollectionName(e.target.value)}
            placeholder="New collection name..."
            aria-label="New collection name"
            className="bg-slate-900 border border-slate-700 rounded px-3 py-1.5 text-xs text-slate-100"
          />
          <button
            type="submit"
            className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono border border-slate-700"
          >
            + Collection
          </button>
        </form>
      </div>

      <form
        onSubmit={(e) => void handleImport(e)}
        className="bg-slate-900/60 border border-slate-800 rounded-lg p-4 flex flex-wrap items-center gap-3"
      >
        <input
          type="text"
          value={importPath}
          onChange={(e) => setImportPath(e.target.value)}
          placeholder="Local video file or folder path (e.g. ./sample.mp4)"
          aria-label="Local video file or folder path"
          className="flex-1 min-w-[260px] bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm font-mono text-slate-100"
        />
        <select
          aria-label="Filter by collection"
          value={selectedCollection}
          onChange={(e) => setSelectedCollection(e.target.value)}
          className="bg-slate-950 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200"
        >
          <option value="">All Collections</option>
          {collections.map((col) => (
            <option key={col.id} value={col.id}>
              {col.name} ({col.video_count})
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="px-4 py-2 rounded bg-indigo-600 hover:bg-indigo-500 text-sm font-medium text-white"
        >
          Import Local Media
        </button>
      </form>

      {statusMessage && (
        <div className="bg-emerald-950/30 border border-emerald-800/50 text-emerald-300 rounded px-4 py-2 text-xs font-mono">
          {statusMessage}
        </div>
      )}
      {errorMessage && (
        <div className="bg-rose-950/30 border border-rose-800/50 text-rose-300 rounded px-4 py-2 text-xs font-mono">
          {errorMessage}
        </div>
      )}

      {selectedVideo && (
        <div
          data-testid="video-inspector-player"
          className="bg-slate-900/70 border border-slate-800 rounded-lg p-5 grid grid-cols-1 lg:grid-cols-3 gap-6"
        >
          <div className="lg:col-span-2 space-y-3">
            <video
              ref={videoRef}
              key={selectedVideo.id}
              controls
              preload="metadata"
              src={getVideoStreamUrl(selectedVideo.id)}
              className="w-full rounded bg-black aspect-video border border-slate-800"
            />
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2">
                <label htmlFor="timestamp-jump-input" className="text-slate-400 font-mono">
                  Jump to (sec):
                </label>
                <input
                  id="timestamp-jump-input"
                  type="number"
                  step="0.5"
                  min="0"
                  value={jumpSeconds}
                  onChange={(e) => setJumpSeconds(e.target.value)}
                  className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 font-mono text-slate-100"
                />
                <button
                  type="button"
                  onClick={() => handleTimestampJump( Number(jumpSeconds) || 0 )}
                  className="px-2.5 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600/50 border border-indigo-500/40 text-indigo-200 font-mono"
                >
                  Seek Player
                </button>
              </div>
              <span className="font-mono text-slate-500">
                SHA-256: {selectedVideo.file_hash.slice(0, 12)}...
              </span>
            </div>
          </div>

          <div className="space-y-2 text-xs font-mono">
            <h3 className="text-sm font-sans font-semibold text-white">
              {selectedVideo.filename}
            </h3>
            <p className="text-slate-400 break-all">{selectedVideo.file_path}</p>
            <div className="border-t border-slate-800 pt-2 space-y-1 text-slate-300">
              <div>Duration: {formatDuration(selectedVideo.duration)} ({selectedVideo.duration}s)</div>
              <div>Resolution: {selectedVideo.width}x{selectedVideo.height}</div>
              <div>Frame Rate: {selectedVideo.fps} fps</div>
              <div>Codec / Format: {selectedVideo.codec} / {selectedVideo.format}</div>
              <div>Size: {(selectedVideo.file_size / 1024).toFixed(1)} KB</div>
              <div>Status: {selectedVideo.processing_status}</div>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-300">
          Indexed Videos ({videos.length})
        </h3>

        {loading ? (
          <p className="text-sm text-slate-400">Loading indexed videos...</p>
        ) : videos.length === 0 ? (
          <p className="text-sm text-slate-500 border border-slate-800 rounded-lg p-6 text-center">
            No videos indexed yet. Enter a local video path above to probe and index.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {videos.map((v) => (
              <div
                key={v.id}
                data-testid={`video-card-${v.id}`}
                className={`border rounded-lg p-4 flex gap-4 bg-slate-900/40 ${
                  selectedVideo?.id === v.id ? "border-indigo-500/60" : "border-slate-800"
                }`}
              >
                <img
                  src={getVideoThumbnailUrl(v.id)}
                  alt={v.filename}
                  className="w-28 h-20 object-cover rounded bg-slate-950 border border-slate-800 shrink-0"
                />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="font-medium text-sm text-white truncate">{v.filename}</div>
                  <div className="text-xs font-mono text-slate-400">
                    {v.width}x{v.height} · {v.fps}fps · {v.codec} · {formatDuration(v.duration)}
                  </div>
                  <div className="pt-2 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedVideo(v)}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-200"
                    >
                      Inspect &amp; Play
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteIndex(v.id)}
                      className="px-2.5 py-1 rounded bg-rose-950/50 hover:bg-rose-900/60 border border-rose-800/50 text-xs font-mono text-rose-300"
                    >
                      Remove Index
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


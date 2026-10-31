import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  type CollectionItem,
  createCollection,
  deleteVideoIndex,
  fetchCollections,
  fetchVideos,
  fetchVideoScenes,
  fetchVideoTranscript,
  getVideoStreamUrl,
  getVideoThumbnailUrl,
  importVideos,
  processVideo,
  type TranscriptItem,
  type VideoItem,
  type VideoSceneItem,
} from "../../services/api";

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function MediaLibraryView() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>("" );
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);

  const [transcript, setTranscript] = useState<TranscriptItem | null>(null);
  const [scenes, setScenes] = useState<VideoSceneItem[]>([]);
  const [processing, setProcessing] = useState<boolean>(false);

  const [importPath, setImportPath] = useState<string>("");
  const [newCollectionName, setNewCollectionName] = useState<string>("");
  const [jumpSeconds, setJumpSeconds] = useState<string>("0");
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [copiedClipId, setCopiedClipId] = useState<string | null>(null);

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

  useEffect(() => {
    if (!selectedVideo) {
      setTranscript(null);
      setScenes([]);
      return;
    }
    void Promise.all([
      fetchVideoTranscript(selectedVideo.id)
        .then(setTranscript)
        .catch(() => setTranscript(null)),
      fetchVideoScenes(selectedVideo.id)
        .then(setScenes)
        .catch(() => setScenes([])),
    ]);
  }, [selectedVideo]);

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

  async function handleProcessVideo() {
    if (!selectedVideo) return;
    setProcessing(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      await processVideo(selectedVideo.id);
      setStatusMessage("Video processing complete. Transcripts and scenes extracted.");
      const [t, s] = await Promise.all([
        fetchVideoTranscript(selectedVideo.id),
        fetchVideoScenes(selectedVideo.id),
      ]);
      setTranscript(t);
      setScenes(s);
      await loadLibrary(selectedCollection);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Video processing failed");
    } finally {
      setProcessing(false);
    }
  }

  function handleTimestampJump(seconds: number) {
    const clamped = Math.max(0, seconds);
    setJumpSeconds(String(clamped));
    if (videoRef.current) {
      videoRef.current.currentTime = clamped;
      try {
        const p = videoRef.current.play();
        if (p && typeof p.catch === "function") {
          p.catch(() => {});
        }
      } catch {
        // Ignored in test environments or autoplay blocked
      }
    }
  }

  function copyMarkdownClip(seg: { start_time: number; end_time: number; text: string }) {
    if (!selectedVideo) return;
    const md = `> **[${selectedVideo.filename}](${getVideoStreamUrl(selectedVideo.id)}#t=${seg.start_time.toFixed(1)})** (${seg.start_time.toFixed(1)}s - ${seg.end_time.toFixed(1)}s)\n> "${seg.text}"\n`;
    void navigator.clipboard.writeText(md);
    setCopiedClipId(`${seg.start_time}`);
    setTimeout(() => setCopiedClipId(null), 2000);
  }

  return (
    <div className="space-y-6">
      {/* Header bar with actions */}
      <div className="border-b border-slate-800/80 pb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-xl font-semibold tracking-tight text-slate-100">
              Studio Media Library
            </h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono text-slate-300 bg-slate-850 border border-slate-750">
              {videos.length} Video{videos.length === 1 ? "" : "s"}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time FFmpeg probe, Faster-Whisper ASR, scene segmentation, and HTTP 206 chunked playback.
          </p>
        </div>

        <form onSubmit={(e) => void handleCreateCollection(e)} className="flex items-center gap-2">
          <input
            type="text"
            value={newCollectionName}
            onChange={(e) => setNewCollectionName(e.target.value)}
            placeholder="New collection tag..."
            aria-label="New collection name"
            className="bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          />
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-xs font-mono font-medium text-slate-200 border border-slate-700 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          >
            + Collection
          </button>
        </form>
      </div>

      {/* Import Form */}
      <form
        onSubmit={(e) => void handleImport(e)}
        className="hallmark-surface p-3.5 flex flex-wrap items-center gap-2.5"
      >
        <div className="relative flex-1 min-w-[280px]">
          <input
            type="text"
            value={importPath}
            onChange={(e) => setImportPath(e.target.value)}
            placeholder="Local video file or folder path (e.g. ./sample_data/demo.mp4)"
            aria-label="Local video file or folder path"
            className="w-full bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-500 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
          />
        </div>
        <select
          aria-label="Filter by collection"
          value={selectedCollection}
          onChange={(e) => setSelectedCollection(e.target.value)}
          className="bg-slate-900 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
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
          className="px-4 py-2 rounded-lg bg-slate-100 hover:bg-white text-xs font-semibold text-slate-950 transition-colors duration-150 active:scale-95 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
        >
          Import Local Media
        </button>
      </form>

      {/* Status Messages */}
      {statusMessage && (
        <div className="bg-emerald-950/30 border border-emerald-800/60 text-emerald-300 rounded-lg px-3.5 py-2.5 text-xs font-mono flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <span>{statusMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="bg-rose-950/30 border border-rose-800/60 text-rose-300 rounded-lg px-3.5 py-2.5 text-xs font-mono flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Studio Video Inspector */}
      {selectedVideo && (
        <div
          data-testid="video-inspector-player"
          className="hallmark-surface p-5 space-y-5"
        >
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
            {/* Left 7 cols: Video Player + Playback HUD */}
            <div className="lg:col-span-7 space-y-3">
              <div className="relative rounded-lg overflow-hidden bg-black aspect-video border border-slate-800">
                <video
                  ref={videoRef}
                  key={selectedVideo.id}
                  controls
                  preload="metadata"
                  src={getVideoStreamUrl(selectedVideo.id)}
                  onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
                  className="w-full h-full object-contain"
                />
              </div>

              {/* Timestamp Jump Controller */}
              <div className="flex flex-wrap items-center justify-between gap-2.5 text-xs bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/70">
                <div className="flex items-center gap-2">
                  <label htmlFor="timestamp-jump-input" className="text-slate-400 font-mono text-[11px]">
                    Jump to (sec):
                  </label>
                  <input
                    id="timestamp-jump-input"
                    type="number"
                    step="0.5"
                    min="0"
                    value={jumpSeconds}
                    onChange={(e) => setJumpSeconds(e.target.value)}
                    className="w-20 bg-slate-900 border border-slate-700/80 rounded px-2 py-0.5 font-mono text-xs text-slate-100 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => handleTimestampJump(Number(jumpSeconds) || 0)}
                    className="px-2.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-mono text-[11px] transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                  >
                    Seek Player
                  </button>
                </div>

                <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400">
                  <span className="text-emerald-400 font-medium">{currentTime.toFixed(1)}s</span>
                  <span>/</span>
                  <span>{selectedVideo.duration.toFixed(1)}s</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-500">SHA-256: {selectedVideo.file_hash.slice(0, 8)}...</span>
                </div>
              </div>
            </div>

            {/* Right 5 cols: Video Metadata Specs & Processing Trigger */}
            <div className="lg:col-span-5 flex flex-col justify-between space-y-3 p-4 rounded-lg border border-slate-800/80 bg-slate-900/40 font-mono text-xs">
              <div>
                <div className="flex items-start justify-between gap-2 border-b border-slate-800/80 pb-2.5">
                  <div>
                    <h3 className="text-sm font-sans font-semibold text-white truncate">
                      {selectedVideo.filename}
                    </h3>
                    <p className="text-[11px] text-slate-400 break-all font-mono mt-0.5">
                      {selectedVideo.file_path}
                    </p>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                    selectedVideo.processing_status === "completed"
                      ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
                      : "bg-amber-950/80 text-amber-400 border border-amber-800/60"
                  }`}>
                    {selectedVideo.processing_status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-2.5 text-slate-300">
                  <div className="p-2 rounded border border-slate-800/80 bg-slate-900/60">
                    <span className="text-slate-500 text-[10px] block">Resolution</span>
                    <span className="text-xs font-medium text-slate-200">{selectedVideo.width}x{selectedVideo.height}</span>
                  </div>
                  <div className="p-2 rounded border border-slate-800/80 bg-slate-900/60">
                    <span className="text-slate-500 text-[10px] block">Duration</span>
                    <span className="text-xs font-medium text-slate-200">{formatDuration(selectedVideo.duration)} ({selectedVideo.duration}s)</span>
                  </div>
                  <div className="p-2 rounded border border-slate-800/80 bg-slate-900/60">
                    <span className="text-slate-500 text-[10px] block">Frame Rate</span>
                    <span className="text-xs font-medium text-slate-200">{selectedVideo.fps} fps</span>
                  </div>
                  <div className="p-2 rounded border border-slate-800/80 bg-slate-900/60">
                    <span className="text-slate-500 text-[10px] block">Codec / Size</span>
                    <span className="text-xs font-medium text-slate-200">{selectedVideo.codec} ({(selectedVideo.file_size / 1024).toFixed(0)} KB)</span>
                  </div>
                </div>

                <div className="mt-2.5 text-[11px] text-slate-400 space-y-0.5">
                  <div>Status: {selectedVideo.processing_status}</div>
                  <div>Format: {selectedVideo.format}</div>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => void handleProcessVideo()}
                  disabled={processing}
                  className="w-full py-2 px-3.5 rounded-lg bg-slate-100 hover:bg-white text-slate-950 font-sans font-semibold text-xs disabled:opacity-50 transition-colors duration-150 flex items-center justify-center gap-2 active:scale-95 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                >
                  {processing ? (
                    <>
                      <span className="h-3 w-3 rounded-full border-2 border-slate-900/30 border-t-slate-900 animate-spin" />
                      <span>Extracting Audio, Scenes &amp; ASR...</span>
                    </>
                  ) : (
                    <span>Process Video (ASR + Scenes)</span>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Scene cut detection strip */}
          <div className="border-t border-slate-800/80 pt-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                <h4 className="text-xs font-medium text-slate-200">
                  Visual Scene Cuts ({scenes.length})
                </h4>
              </div>
              <span className="text-[11px] text-slate-400 font-mono">
                Click scene to seek
              </span>
            </div>

            {scenes.length === 0 ? (
              <p className="text-xs text-slate-500 font-mono bg-slate-900/30 p-2.5 rounded border border-slate-800/60">
                No scenes detected yet. Click &quot;Process Video&quot; above to run PySceneDetect.
              </p>
            ) : (
              <div className="flex gap-2 overflow-x-auto pb-1.5">
                {scenes.map((scene) => (
                  <button
                    key={scene.id}
                    type="button"
                    onClick={() => handleTimestampJump(scene.start_time)}
                    className="shrink-0 text-left bg-slate-900/80 border border-slate-800 hover:border-slate-700 rounded-lg p-2 text-xs font-mono transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                  >
                    <div className="text-amber-400 font-medium">
                      Scene #{scene.scene_index + 1}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      {scene.start_time.toFixed(1)}s - {scene.end_time.toFixed(1)}s
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Synchronized Real-Time Transcript Segments */}
          <div className="border-t border-slate-800/80 pt-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                <h4 className="text-xs font-medium text-slate-200">
                  Synchronized Transcript ({transcript?.segments.length ?? 0} Segments)
                </h4>
              </div>
              {transcript && (
                <span className="text-[11px] text-slate-400 font-mono">
                  {transcript.language} · {transcript.model_name}
                </span>
              )}
            </div>

            {!transcript || transcript.segments.length === 0 ? (
              <p className="text-xs text-slate-500 font-mono bg-slate-900/30 p-2.5 rounded border border-slate-800/60">
                No transcript available yet. Click &quot;Process Video&quot; above to transcribe.
              </p>
            ) : (
              <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
                {transcript.segments.map((seg) => {
                  const isActive = currentTime >= seg.start_time && currentTime <= seg.end_time;
                  return (
                    <div
                      key={seg.id}
                      data-testid={`transcript-segment-${seg.id}`}
                      onClick={() => handleTimestampJump(seg.start_time)}
                      className={`w-full text-left p-2.5 rounded-lg border flex items-center justify-between gap-2.5 transition-colors duration-150 cursor-pointer text-xs ${
                        isActive
                          ? "bg-slate-800 border-slate-600 text-white"
                          : "bg-slate-900/40 border-slate-800 hover:border-slate-700 text-slate-300"
                      }`}
                    >
                      <div className="flex items-start gap-2.5 flex-1 min-w-0">
                        <span className={`font-mono shrink-0 text-[11px] px-1.5 py-0.5 rounded ${
                          isActive
                            ? "bg-slate-900 text-slate-200 font-medium"
                            : "bg-slate-950 text-slate-400 border border-slate-800"
                        }`}>
                          {seg.start_time.toFixed(1)}s - {seg.end_time.toFixed(1)}s
                        </span>
                        <span className={`leading-relaxed ${isActive ? "font-medium text-white" : "text-slate-300"}`}>
                          {seg.text}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          copyMarkdownClip(seg);
                        }}
                        className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-750 border border-slate-700 text-[10px] font-mono text-slate-400 hover:text-white shrink-0 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                      >
                        {copiedClipId === `${seg.start_time}` ? "Copied!" : "Quote MD"}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Grid of Indexed Videos */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-slate-300">
            Video Archive ({videos.length})
          </h3>
          <span className="text-[11px] text-slate-500 font-mono">
            Direct Local Indexing
          </span>
        </div>

        {loading ? (
          <p className="text-xs text-slate-400 font-mono">Scanning media library...</p>
        ) : videos.length === 0 ? (
          <div className="hallmark-surface border-dashed border-slate-800 p-8 text-center space-y-1">
            <p className="text-xs text-slate-300 font-medium">No videos indexed in this collection yet.</p>
            <p className="text-[11px] text-slate-500 font-mono">
              Provide an absolute or relative video path in the bar above to start indexing.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {videos.map((v) => {
              const isSelected = selectedVideo?.id === v.id;
              return (
                <div
                  key={v.id}
                  data-testid={`video-card-${v.id}`}
                  className={`hallmark-surface p-3 flex gap-3 transition-colors duration-150 ${
                    isSelected
                      ? "border-slate-600 bg-slate-850"
                      : "hover:border-slate-700"
                  }`}
                >
                  <img
                    src={getVideoThumbnailUrl(v.id)}
                    alt={v.filename}
                    className="w-28 h-20 object-cover rounded bg-black border border-slate-800 shrink-0"
                  />
                  <div className="flex-1 min-w-0 flex flex-col justify-between">
                    <div>
                      <div className="font-medium text-xs text-white truncate">{v.filename}</div>
                      <div className="text-[11px] font-mono text-slate-400 mt-0.5">
                        {v.width}x{v.height} · {v.fps}fps · {v.codec} · {formatDuration(v.duration)}
                      </div>
                    </div>

                    <div className="pt-2 flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setSelectedVideo(v)}
                        className={`px-2.5 py-1 rounded text-xs font-mono font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none ${
                          isSelected
                            ? "bg-slate-100 text-slate-950 font-semibold"
                            : "bg-slate-800 hover:bg-slate-700 text-slate-200"
                        }`}
                      >
                        Inspect &amp; Play
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDeleteIndex(v.id)}
                        className="px-2 py-1 rounded bg-rose-950/30 hover:bg-rose-900/40 border border-rose-800/40 text-xs font-mono text-rose-300 transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
                      >
                        Remove Index
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

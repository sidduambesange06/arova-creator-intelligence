import { useEffect, useRef, useState } from "react";
import {
  createAnnotation,
  exportVideoClip,
  fetchAnnotations,
  fetchVideoScenes,
  fetchVideos,
  fetchVideoTranscript,
  getClipDownloadUrl,
  getVideoStreamUrl,
  getVideoThumbnailUrl,
  summarizeVideo,
  uploadVideoSubtitles,
  type AnnotationItem,
  type ClipExportResponse,
  type VideoItem,
  type VideoSceneItem,
  type VideoSummaryResponse,
} from "../../services/api";

function formatSMPTE(sec: number, fps = 30): string {
  const totalFrames = Math.max(0, Math.floor(sec * fps));
  const f = totalFrames % fps;
  const s = Math.floor(sec) % 60;
  const m = Math.floor(sec / 60) % 60;
  const h = Math.floor(sec / 3600);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

interface VideoWorkstationViewProps {
  initialVideoId?: string;
}

export function VideoWorkstationView({ initialVideoId }: VideoWorkstationViewProps) {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);
  const [transcript, setTranscript] = useState<any | null>(null);
  const [scenes, setScenes] = useState<VideoSceneItem[]>([]);
  const [annotations, setAnnotations] = useState<AnnotationItem[]>([]);
  const [summary, setSummary] = useState<VideoSummaryResponse | null>(null);

  // Player State
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  // In / Out markers for lossless clip export
  const [inPoint, setInPoint] = useState<number | null>(null);
  const [outPoint, setOutPoint] = useState<number | null>(null);
  const [exportingClip, setExportingClip] = useState(false);
  const [clipResult, setClipResult] = useState<ClipExportResponse | null>(null);
  const [clipError, setClipError] = useState<string | null>(null);

  // Subtitle Sidecar Attach Form
  const [showSubModal, setShowSubModal] = useState(false);
  const [subContent, setSubContent] = useState("");
  const [subFilename, setSubFilename] = useState("subtitles.srt");
  const [subLanguage, setSubLanguage] = useState("en");
  const [submittingSub, setSubmittingSub] = useState(false);
  const [subMsg, setSubMsg] = useState<string | null>(null);

  // Annotation Note State
  const [noteBody, setNoteBody] = useState("");
  const [addingNote, setAddingNote] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadVideos() {
      try {
        const vids = await fetchVideos();
        if (cancelled) return;
        setVideos(vids);
        if (vids.length > 0) {
          const match = initialVideoId
            ? vids.find((v) => v.id === initialVideoId) ?? vids[0]
            : vids[0];
          setSelectedVideo(match);
        }
      } catch {
        // Handled silently
      }
    }
    void loadVideos();
    return () => {
      cancelled = true;
    };
  }, [initialVideoId]);

  useEffect(() => {
    if (!selectedVideo) return;
    const currentVidId = selectedVideo.id;
    let cancelled = false;
    async function loadIntelligence() {
      try {
        const [trans, sc, ann] = await Promise.all([
          fetchVideoTranscript(currentVidId).catch(() => null),
          fetchVideoScenes(currentVidId).catch(() => []),
          fetchAnnotations(currentVidId).catch(() => []),
        ]);
        if (!cancelled) {
          setTranscript(trans);
          setScenes(sc);
          setAnnotations(ann);
          setSummary(null);
          setClipResult(null);
          setInPoint(null);
          setOutPoint(null);
        }
      } catch {
        // Handled
      }
    }
    void loadIntelligence();
    return () => {
      cancelled = true;
    };
  }, [selectedVideo]);

  function handleTimeUpdate() {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
      setDuration(videoRef.current.duration || selectedVideo?.duration || 0);
    }
  }

  function handleSeek(targetSec: number) {
    const clamped = Math.max(0, Math.min(targetSec, duration || selectedVideo?.duration || 0));
    if (videoRef.current) {
      videoRef.current.currentTime = clamped;
    }
    setCurrentTime(clamped);
  }

  function togglePlay() {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => setIsPlaying(false));
    }
  }

  async function handleExportClip() {
    if (!selectedVideo) return;
    const start = inPoint ?? 0;
    const end = outPoint ?? (duration || selectedVideo.duration);
    if (start >= end) {
      setClipError("In point must be strictly less than Out point.");
      return;
    }
    setExportingClip(true);
    setClipError(null);
    try {
      const res = await exportVideoClip(selectedVideo.id, start, end);
      setClipResult(res);
    } catch (err) {
      setClipError(err instanceof Error ? err.message : "Clip export failed");
    } finally {
      setExportingClip(false);
    }
  }

  async function handleAttachSubtitles(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedVideo || !subContent.trim()) return;
    setSubmittingSub(true);
    setSubMsg(null);
    try {
      const newTrans = await uploadVideoSubtitles(
        selectedVideo.id,
        subContent.trim(),
        subFilename.trim() || "subtitles.srt",
        subLanguage.trim() || "en"
      );
      setTranscript(newTrans);
      setSubMsg("Subtitles attached successfully.");
      setSubContent("");
      setShowSubModal(false);
    } catch (err) {
      setSubMsg(err instanceof Error ? err.message : "Failed to upload subtitles");
    } finally {
      setSubmittingSub(false);
    }
  }

  async function handleCreateAnnotation(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedVideo || !noteBody.trim()) return;
    setAddingNote(true);
    try {
      const note = await createAnnotation({
        target_type: "version",
        target_id: selectedVideo.id,
        display_name: `Timecode Note @ ${formatSMPTE(currentTime, selectedVideo.fps)}`,
        body: noteBody.trim(),
      });
      setAnnotations((prev) => [note, ...prev]);
      setNoteBody("");
    } catch (err) {
      // Handled
    } finally {
      setAddingNote(false);
    }
  }

  async function handleGenerateSummary() {
    if (!selectedVideo) return;
    try {
      const s = await summarizeVideo(selectedVideo.id);
      setSummary(s);
    } catch {
      // Handled
    }
  }

  if (videos.length === 0) {
    return (
      <div className="p-8 rounded-panel bg-[#111827] border border-[#243149] text-center space-y-3 font-mono text-xs">
        <p className="text-slate-400">No media indexed in the workstation library.</p>
        <p className="text-[11px] text-slate-500">
          Import videos in the Overview or Media Library to activate the Precision Instrument.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Controls Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-panel bg-[#111827] border border-[#243149]">
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-300">Active Video:</label>
          <select
            value={selectedVideo?.id ?? ""}
            onChange={(e) => {
              const match = videos.find((v) => v.id === e.target.value);
              if (match) setSelectedVideo(match);
            }}
            className="px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#F5F7FB] focus:border-[#9B8CFF] focus:outline-none"
          >
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.filename} ({v.duration.toFixed(1)}s Â· {v.width}x{v.height})
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowSubModal(true)}
            className="px-3 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#51DCC8] border border-[#243149] transition-colors"
          >
            + Attach Subtitles (.srt)
          </button>
          <button
            type="button"
            onClick={handleGenerateSummary}
            className="px-3 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#9B8CFF] border border-[#243149] transition-colors"
          >
            Generate AI Summary
          </button>
        </div>
      </div>

      {/* Main Workstation Screen: Video Player & Inspector */}
      {selectedVideo && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Precision Video Canvas */}
          <div className="lg:col-span-2 space-y-3">
            <div className="relative rounded-panel overflow-hidden bg-black border border-[#243149] aspect-video flex items-center justify-center shadow-lg">
              <video
                ref={videoRef}
                src={getVideoStreamUrl(selectedVideo.id)}
                poster={getVideoThumbnailUrl(selectedVideo.id)}
                onTimeUpdate={handleTimeUpdate}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                className="w-full h-full object-contain"
                controls={false}
              />

              {/* SMPTE Timecode HUD Overlay */}
              <div className="absolute top-3 left-3 px-2 py-1 rounded bg-[#080B12]/80 backdrop-blur border border-[#243149] text-xs font-mono text-[#51DCC8]">
                {formatSMPTE(currentTime, selectedVideo.fps)}
              </div>

              <div className="absolute top-3 right-3 px-2 py-1 rounded bg-[#080B12]/80 backdrop-blur border border-[#243149] text-[11px] font-mono text-slate-300">
                {selectedVideo.width}x{selectedVideo.height} Â· {selectedVideo.fps}fps Â· {selectedVideo.codec}
              </div>
            </div>

            {/* Transport Bar & Scrubber */}
            <div className="p-3 rounded-panel bg-[#111827] border border-[#243149] space-y-2">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={togglePlay}
                  className="px-3 py-1 rounded-control bg-[#9B8CFF] text-[#080B12] text-xs font-semibold"
                >
                  {isPlaying ? "Pause" : "Play"}
                </button>
                <input
                  type="range"
                  min={0}
                  max={duration || selectedVideo.duration || 1}
                  step={0.01}
                  value={currentTime}
                  onChange={(e) => handleSeek(parseFloat(e.target.value))}
                  className="flex-1 studio-scrubber"
                />
                <span className="text-xs font-mono text-[#F5F7FB]">
                  {currentTime.toFixed(2)}s / {(duration || selectedVideo.duration).toFixed(2)}s
                </span>
              </div>

              {/* In / Out Clip Selection Transport */}
              <div className="flex flex-wrap items-center justify-between text-xs font-mono pt-1 border-t border-[#243149]/50">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setInPoint(currentTime)}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    Set In: {inPoint !== null ? `${inPoint.toFixed(2)}s` : "--"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setOutPoint(currentTime)}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    Set Out: {outPoint !== null ? `${outPoint.toFixed(2)}s` : "--"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setInPoint(null);
                      setOutPoint(null);
                    }}
                    className="text-[10px] text-slate-500 hover:text-slate-300 underline"
                  >
                    Clear Markers
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={handleExportClip}
                    disabled={exportingClip}
                    className="px-3 py-1 rounded-control bg-[#172235] hover:bg-[#232f48] text-[#F5F7FB] border border-[#243149] disabled:opacity-50"
                  >
                    {exportingClip ? "Exporting Lossless..." : "Export Lossless MP4 Clip"}
                  </button>
                </div>
              </div>

              {clipResult && (
                <div className="p-2.5 rounded bg-[#0B1019] border border-emerald-900/50 text-emerald-300 text-xs font-mono flex items-center justify-between">
                  <span>Clip ready: {clipResult.clip_filename} ({clipResult.duration.toFixed(1)}s)</span>
                  <a
                    href={getClipDownloadUrl(clipResult.clip_filename)}
                    download
                    className="px-2 py-0.5 rounded bg-emerald-900 text-emerald-200 hover:bg-emerald-800"
                  >
                    Download MP4
                  </a>
                </div>
              )}

              {clipError && (
                <div className="p-2 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-xs font-mono">
                  {clipError}
                </div>
              )}
            </div>

            {/* Multi-Track Intelligence Timeline */}
            <div className="p-4 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
              <h3 className="text-xs font-semibold text-[#F5F7FB] tracking-tight">
                Multi-Track Intelligence Timeline
              </h3>

              {/* Track 1: Speech Transcript & Subtitles */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#51DCC8]" />
                    Speech Transcript &amp; Dialogue
                  </span>
                  <span>{transcript?.segments?.length ?? 0} segments</span>
                </div>

                <div className="max-h-36 overflow-y-auto space-y-1 p-2 rounded bg-[#0B1019] border border-[#243149]">
                  {transcript?.segments?.length ? (
                    transcript.segments.map((seg: any) => {
                      const isActive =
                        currentTime >= seg.start_time && currentTime <= seg.end_time;
                      return (
                        <div
                          key={seg.id}
                          onClick={() => handleSeek(seg.start_time)}
                          className={`p-1.5 rounded cursor-pointer text-xs font-mono transition-colors flex items-start justify-between ${
                            isActive
                              ? "bg-[#51DCC8]/20 border border-[#51DCC8] text-white"
                              : "hover:bg-[#172235] text-slate-300"
                          }`}
                        >
                          <span className="pr-2">{seg.text}</span>
                          <span className="text-[10px] text-slate-500 shrink-0">
                            {seg.start_time.toFixed(1)}s
                          </span>
                        </div>
                      );
                    })
                  ) : (
                    <div className="py-4 text-center text-xs text-slate-500 font-mono">
                      No transcript segments available. Click &quot;+ Attach Subtitles&quot; above to import.
                    </div>
                  )}
                </div>
              </div>

              {/* Track 2: Visual Scene Cuts */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#F4BF69]" />
                    Visual Scene Cuts &amp; Keyframes
                  </span>
                  <span>{scenes.length} cuts</span>
                </div>

                <div className="flex gap-2 overflow-x-auto py-1">
                  {scenes.length ? (
                    scenes.map((sc) => (
                      <div
                        key={sc.id}
                        onClick={() => handleSeek(sc.start_time)}
                        className="p-1.5 rounded bg-[#0B1019] hover:bg-[#172235] border border-[#243149] shrink-0 cursor-pointer text-center space-y-1"
                      >
                        <div className="w-20 h-12 bg-black rounded overflow-hidden flex items-center justify-center text-[10px] text-slate-500 font-mono">
                          Scene #{sc.scene_index + 1}
                        </div>
                        <p className="text-[10px] font-mono text-slate-400">
                          {sc.start_time.toFixed(1)}s
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="py-2 text-xs text-slate-500 font-mono">
                      No scene cuts recorded.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Metadata Inspector & User Notes */}
          <div className="space-y-4">
            {/* Asset Forensic Specs */}
            <div className="p-4 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
              <h3 className="text-xs font-semibold text-[#F5F7FB]">Forensic Metadata</h3>
              <dl className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">Container</dt>
                  <dd className="text-slate-200 mt-0.5">{selectedVideo.format}</dd>
                </div>
                <div className="p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">Video Codec</dt>
                  <dd className="text-slate-200 mt-0.5">{selectedVideo.codec}</dd>
                </div>
                <div className="p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">Frame Rate</dt>
                  <dd className="text-slate-200 mt-0.5">{selectedVideo.fps} fps</dd>
                </div>
                <div className="p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">File Size</dt>
                  <dd className="text-slate-200 mt-0.5">
                    {(selectedVideo.file_size / (1024 * 1024)).toFixed(1)} MB
                  </dd>
                </div>
                <div className="col-span-2 p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">SHA-256 Digest</dt>
                  <dd className="text-slate-300 mt-0.5 break-all text-[10px]">
                    {selectedVideo.file_hash}
                  </dd>
                </div>
                <div className="col-span-2 p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">Source Path</dt>
                  <dd className="text-slate-300 mt-0.5 break-all text-[10px]">
                    {selectedVideo.file_path}
                  </dd>
                </div>
              </dl>
            </div>

            {/* AI Summary Output if present */}
            {summary && (
              <div className="p-4 rounded-panel bg-[#111827] border border-[#9B8CFF]/40 space-y-2">
                <div className="flex items-center justify-between text-xs font-semibold text-[#9B8CFF]">
                  <span>AI Video Summary</span>
                  <span className="text-[10px] font-mono text-slate-400">
                    {summary.model_name}
                  </span>
                </div>
                <p className="text-xs text-slate-200 leading-relaxed">{summary.summary}</p>
                {summary.topics?.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {summary.topics.map((t) => (
                      <span
                        key={t}
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#0B1019] text-[#9B8CFF] border border-[#9B8CFF]/30"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Timecode Annotations & Notes */}
            <div className="p-4 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
              <h3 className="text-xs font-semibold text-[#F5F7FB]">Annotations &amp; Notes</h3>

              <form onSubmit={handleCreateAnnotation} className="space-y-2">
                <textarea
                  rows={2}
                  required
                  value={noteBody}
                  onChange={(e) => setNoteBody(e.target.value)}
                  placeholder={`Add note at ${formatSMPTE(currentTime, selectedVideo.fps)}...`}
                  className="w-full px-2.5 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-[#F5F7FB] font-sans focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={addingNote || !noteBody.trim()}
                  className="w-full py-1 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#F5F7FB] border border-[#243149] disabled:opacity-50"
                >
                  {addingNote ? "Saving..." : "+ Save Marker Note"}
                </button>
              </form>

              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {annotations.map((ann) => (
                  <div
                    key={ann.id}
                    className="p-2 rounded bg-[#0B1019] border border-[#243149] text-xs space-y-0.5"
                  >
                    <div className="flex items-center justify-between text-[10px] font-mono text-[#9B8CFF]">
                      <span>{ann.display_name}</span>
                      <span className="text-slate-500">{ann.author_type}</span>
                    </div>
                    <p className="text-slate-200">{ann.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Attach Subtitles Modal */}
      {showSubModal && selectedVideo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md bg-[#111827] border border-[#243149] rounded-panel p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#243149] pb-2">
              <h3 className="text-xs font-semibold text-[#F5F7FB]">
                Attach Subtitles to {selectedVideo.filename}
              </h3>
              <button
                type="button"
                onClick={() => setShowSubModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                âœ•
              </button>
            </div>

            {subMsg && (
              <div className="p-2 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8]">
                {subMsg}
              </div>
            )}

            <form onSubmit={handleAttachSubtitles} className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] text-slate-300 font-mono">Filename:</label>
                  <input
                    type="text"
                    value={subFilename}
                    onChange={(e) => setSubFilename(e.target.value)}
                    className="w-full px-2 py-1 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-slate-300 font-mono">Language:</label>
                  <input
                    type="text"
                    value={subLanguage}
                    onChange={(e) => setSubLanguage(e.target.value)}
                    className="w-full px-2 py-1 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] text-slate-300 font-mono">Raw SRT/WebVTT:</label>
                <textarea
                  rows={6}
                  required
                  value={subContent}
                  onChange={(e) => setSubContent(e.target.value)}
                  placeholder={"1\n00:00:00,000 --> 00:00:05,000\nSubtitles here..."}
                  className="w-full px-2 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowSubModal(false)}
                  className="px-3 py-1 rounded bg-[#172235] text-xs text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingSub}
                  className="px-3 py-1 rounded bg-[#51DCC8] text-[#080B12] text-xs font-semibold"
                >
                  {submittingSub ? "Saving..." : "Upload Subtitles"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

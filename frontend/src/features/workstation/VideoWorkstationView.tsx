import { useEffect, useRef, useState } from "react";
import {
  createAnnotation,
  exportVideoClip,
  exportVideoSubtitles,
  fetchAnnotations,
  fetchVideoOcrStatus,
  fetchVideoScenes,
  fetchVideos,
  fetchVideoTranscript,
  getClipDownloadUrl,
  getSceneThumbnailUrl,
  getVideoStreamUrl,
  getVideoThumbnailUrl,
  processVideo,
  summarizeVideo,
  uploadVideoSubtitles,
  type AnnotationItem,
  type ClipExportResponse,
  type SubtitleExportFormat,
  type TranscriptItem,
  type TranscriptSegmentItem,
  type VideoItem,
  type VideoOcrStatusItem,
  type VideoSceneItem,
  type VideoSummaryResponse,
} from "../../services/api";

function formatSMPTE(sec: number, fps = 30): string {
  const safeFps = fps > 0 ? Math.round(fps) : 30;
  const totalFrames = Math.max(0, Math.floor(sec * safeFps));
  const f = totalFrames % safeFps;
  const s = Math.floor(sec) % 60;
  const m = Math.floor(sec / 60) % 60;
  const h = Math.floor(sec / 3600);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}:${pad(f)}`;
}

interface VideoWorkstationViewProps {
  initialVideoId?: string;
  initialStartTime?: number;
}

export function VideoWorkstationView({
  initialVideoId,
  initialStartTime,
}: VideoWorkstationViewProps) {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);
  const [transcript, setTranscript] = useState<TranscriptItem | null>(null);
  const [scenes, setScenes] = useState<VideoSceneItem[]>([]);
  const [ocrStatus, setOcrStatus] = useState<VideoOcrStatusItem | null>(null);
  const [annotations, setAnnotations] = useState<AnnotationItem[]>([]);
  const [summary, setSummary] = useState<VideoSummaryResponse | null>(null);
  const [processingPipeline, setProcessingPipeline] = useState(false);
  const [pipelineMsg, setPipelineMsg] = useState<string | null>(null);

  // Subtitle Export State
  const [exportingSubFormat, setExportingSubFormat] = useState<SubtitleExportFormat | null>(null);
  const [subExportError, setSubExportError] = useState<string | null>(null);
  const [subExportSuccess, setSubExportSuccess] = useState<string | null>(null);
  const [includeAssKaraoke, setIncludeAssKaraoke] = useState(false);

  // Player State
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [isMuted, setIsMuted] = useState(false);
  const [playerError, setPlayerError] = useState<string | null>(null);
  const [isPreviewingRange, setIsPreviewingRange] = useState(false);

  // In / Out markers for clip export
  const [inPoint, setInPoint] = useState<number | null>(null);
  const [outPoint, setOutPoint] = useState<number | null>(null);
  const [exportingClip, setExportingClip] = useState(false);
  const [clipResult, setClipResult] = useState<ClipExportResponse | null>(null);
  const [clipError, setClipError] = useState<string | null>(null);

  // Transcript Search Filter
  const [transcriptFilter, setTranscriptFilter] = useState("");

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
        const list = Array.isArray(vids) ? vids : [];
        setVideos(list);
        if (list.length > 0) {
          const match = initialVideoId
            ? list.find((v) => v.id === initialVideoId) ?? list[0]
            : list[0];
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
    setPlayerError(null);
    setPipelineMsg(null);
    setIsPreviewingRange(false);
    async function loadIntelligence() {
      try {
        const [trans, sc, ann, ocr] = await Promise.all([
          fetchVideoTranscript(currentVidId).catch(() => null),
          fetchVideoScenes(currentVidId).catch(() => []),
          fetchAnnotations(currentVidId).catch(() => []),
          fetchVideoOcrStatus(currentVidId).catch(() => null),
        ]);
        if (!cancelled) {
          setTranscript(trans);
          setScenes(Array.isArray(sc) ? sc : []);
          setAnnotations(Array.isArray(ann) ? ann : []);
          setOcrStatus(ocr);
          setSummary(null);
          setClipResult(null);
          setClipError(null);
          setSubExportError(null);
          setSubExportSuccess(null);
          setIncludeAssKaraoke(false);
          setInPoint(null);
          setOutPoint(null);
          if (initialStartTime !== undefined && initialStartTime >= 0) {
            handleSeek(initialStartTime);
          } else {
            setCurrentTime(0);
          }
        }
      } catch {
        // Handled
      }
    }
    void loadIntelligence();
    return () => {
      cancelled = true;
    };
  }, [selectedVideo, initialStartTime]);

  const effectiveDuration = duration || selectedVideo?.duration || 0;
  const frameStep = 1 / Math.max(selectedVideo?.fps || 24, 1);

  function handleTimeUpdate() {
    if (!videoRef.current) return;
    const now = videoRef.current.currentTime;
    setCurrentTime(now);
    if (videoRef.current.duration && Number.isFinite(videoRef.current.duration)) {
      setDuration(videoRef.current.duration);
    }
    if (isPreviewingRange && outPoint !== null && now >= outPoint) {
      videoRef.current.pause();
      videoRef.current.currentTime = outPoint;
      setCurrentTime(outPoint);
      setIsPlaying(false);
      setIsPreviewingRange(false);
    }
  }

  function handleLoadedMetadata() {
    if (!videoRef.current) return;
    if (videoRef.current.duration && Number.isFinite(videoRef.current.duration)) {
      setDuration(videoRef.current.duration);
    }
    videoRef.current.playbackRate = playbackRate;
    setPlayerError(null);
  }

  function handleSeek(targetSec: number) {
    const maxDur = effectiveDuration || 0;
    const clamped = Math.max(0, maxDur > 0 ? Math.min(targetSec, maxDur) : targetSec);
    if (videoRef.current) {
      videoRef.current.currentTime = clamped;
    }
    setCurrentTime(clamped);
  }

  function togglePlay() {
    if (!videoRef.current) return;
    setIsPreviewingRange(false);
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

  function handleSpeedChange(rate: number) {
    setPlaybackRate(rate);
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
  }

  function toggleMute() {
    const nextMuted = !isMuted;
    setIsMuted(nextMuted);
    if (videoRef.current) {
      videoRef.current.muted = nextMuted;
    }
  }

  function handleFullscreen() {
    if (videoRef.current && typeof videoRef.current.requestFullscreen === "function") {
      void videoRef.current.requestFullscreen().catch(() => {});
    }
  }

  function handlePreviewSelection() {
    const start = inPoint ?? 0;
    const end = outPoint ?? effectiveDuration;
    if (start >= end) {
      setClipError("In point must be strictly less than Out point to preview selection.");
      return;
    }
    setClipError(null);
    setIsPreviewingRange(true);
    handleSeek(start);
    if (videoRef.current) {
      videoRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch(() => setIsPlaying(false));
    }
  }

  function jumpToAdjacentScene(direction: -1 | 1) {
    if (scenes.length === 0) return;
    const currentIdx = scenes.findIndex(
      (sc) => currentTime >= sc.start_time && currentTime < sc.end_time
    );
    if (currentIdx === -1) {
      handleSeek(scenes[0].start_time);
      return;
    }
    const targetIdx = Math.max(0, Math.min(scenes.length - 1, currentIdx + direction));
    handleSeek(scenes[targetIdx].start_time);
  }

  async function handleRunPipeline() {
    if (!selectedVideo) return;
    setProcessingPipeline(true);
    setPipelineMsg(null);
    try {
      await processVideo(selectedVideo.id);
      const [trans, sc, ocr] = await Promise.all([
        fetchVideoTranscript(selectedVideo.id).catch(() => null),
        fetchVideoScenes(selectedVideo.id).catch(() => []),
        fetchVideoOcrStatus(selectedVideo.id).catch(() => null),
      ]);
      setTranscript(trans);
      setScenes(Array.isArray(sc) ? sc : []);
      setOcrStatus(ocr);
      setPipelineMsg("7-stage intelligence pipeline completed (ASR + Scene Cuts + FTS5).");
    } catch (err) {
      setPipelineMsg(err instanceof Error ? err.message : "Pipeline execution failed");
    } finally {
      setProcessingPipeline(false);
    }
  }

  async function handleExportClip() {
    if (!selectedVideo) return;
    const start = inPoint ?? 0;
    const end = outPoint ?? effectiveDuration;
    if (start < 0) {
      setClipError("In point cannot be negative.");
      return;
    }
    if (start >= end) {
      setClipError("In point must be strictly less than Out point.");
      return;
    }
    if (effectiveDuration > 0 && end > effectiveDuration + 0.05) {
      setClipError(`Out point (${end.toFixed(2)}s) exceeds video duration (${effectiveDuration.toFixed(2)}s).`);
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
    } catch {
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

  async function handleExportSubtitles(format: SubtitleExportFormat) {
    if (!selectedVideo || exportingSubFormat !== null) return;
    if (!transcript || !transcript.segments || transcript.segments.length === 0) {
      setSubExportError("No transcript segments available to export.");
      return;
    }
    setExportingSubFormat(format);
    setSubExportError(null);
    setSubExportSuccess(null);
    let objectUrl: string | null = null;
    try {
      const karaokeEnabled = format === "ass" && includeAssKaraoke && hasWordTimings;
      const { content, mimeType } = await exportVideoSubtitles(
        selectedVideo.id,
        format,
        karaokeEnabled
      );
      const stem = selectedVideo.filename.replace(/\.[^.]+$/, "") || selectedVideo.id;
      const downloadName = `${stem}.${format}`;
      const blob = new Blob([content], { type: mimeType });
      objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = downloadName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setSubExportSuccess(`Exported ${downloadName}`);
    } catch (err) {
      setSubExportError(err instanceof Error ? err.message : `Failed to export ${format.toUpperCase()} subtitles`);
    } finally {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
      setExportingSubFormat(null);
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

  const allSegments: TranscriptSegmentItem[] = transcript?.segments ?? [];
  const hasWordTimings = allSegments.some(
    (seg) => Array.isArray(seg.words) && seg.words.length > 0
  );
  const timingSummaryLabel = !transcript || allSegments.length === 0
    ? "No timing data"
    : hasWordTimings
      ? "Timing: ASR-estimated word timing (not forced-aligned)"
      : "Timing: Segment-level only (word timings unavailable)";
  const filteredSegments = transcriptFilter.trim()
    ? allSegments.filter((seg) =>
        String(seg.text || "")
          .toLowerCase()
          .includes(transcriptFilter.trim().toLowerCase())
      )
    : allSegments;

  const activeScene = scenes.find(
    (sc) => currentTime >= sc.start_time && currentTime < sc.end_time
  );

  const selectionStartPct =
    effectiveDuration > 0 && inPoint !== null
      ? Math.max(0, Math.min(100, (inPoint / effectiveDuration) * 100))
      : 0;
  const selectionEndPct =
    effectiveDuration > 0 && outPoint !== null
      ? Math.max(0, Math.min(100, (outPoint / effectiveDuration) * 100))
      : 100;

  return (
    <div className="space-y-6">
      {/* Top Controls Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-panel bg-[#111827] border border-[#243149]">
        <div className="flex items-center gap-3 flex-wrap">
          <label htmlFor="workstation-video-select" className="text-xs font-semibold text-slate-300">
            Active Video:
          </label>
          <select
            id="workstation-video-select"
            aria-label="Active Video"
            value={selectedVideo?.id ?? ""}
            onChange={(e) => {
              const match = videos.find((v) => v.id === e.target.value);
              if (match) setSelectedVideo(match);
            }}
            className="px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#F5F7FB] focus:border-[#9B8CFF] focus:outline-none"
          >
            {videos.map((v) => (
              <option key={v.id} value={v.id}>
                {v.filename} ({v.duration.toFixed(1)}s &middot; {v.width}x{v.height})
              </option>
            ))}
          </select>
          {selectedVideo && (
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                selectedVideo.processing_status === "completed"
                  ? "bg-emerald-950/70 text-emerald-300 border border-emerald-800/60"
                  : "bg-amber-950/70 text-amber-300 border border-amber-800/60"
              }`}
            >
              {selectedVideo.processing_status}
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => void handleRunPipeline()}
            disabled={processingPipeline}
            className="px-3 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-slate-200 border border-[#243149] transition-colors disabled:opacity-50"
          >
            {processingPipeline ? "Processing Pipeline..." : "Verify / Re-run Pipeline"}
          </button>
          <button
            type="button"
            onClick={() => setShowSubModal(true)}
            className="px-3 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#51DCC8] border border-[#243149] transition-colors"
          >
            + Attach Subtitles (.srt)
          </button>
          <button
            type="button"
            onClick={() => void handleGenerateSummary()}
            className="px-3 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#9B8CFF] border border-[#243149] transition-colors"
          >
            Generate AI Summary
          </button>
        </div>
      </div>

      {pipelineMsg && (
        <div className="p-2.5 rounded-panel bg-[#111827] border border-[#51DCC8]/40 text-xs font-mono text-[#51DCC8]">
          {pipelineMsg}
        </div>
      )}

      {/* Main Workstation Screen: Video Player & Inspector */}
      {selectedVideo && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Precision Video Canvas */}
          <div className="lg:col-span-2 space-y-3">
            <div className="relative rounded-panel overflow-hidden bg-black border border-[#243149] aspect-video flex items-center justify-center shadow-lg">
              <video
                ref={videoRef}
                key={selectedVideo.id}
                src={getVideoStreamUrl(selectedVideo.id)}
                poster={getVideoThumbnailUrl(selectedVideo.id)}
                onLoadedMetadata={handleLoadedMetadata}
                onTimeUpdate={handleTimeUpdate}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onEnded={() => {
                  setIsPlaying(false);
                  setIsPreviewingRange(false);
                }}
                onError={() =>
                  setPlayerError(
                    `Unable to stream media file (${selectedVideo.filename}). Verify the source file exists on disk.`
                  )
                }
                className="w-full h-full object-contain"
                controls={false}
              />

              {/* SMPTE Timecode HUD Overlay */}
              <div
                data-testid="smpte-hud"
                className="absolute top-3 left-3 px-2 py-1 rounded bg-[#080B12]/80 backdrop-blur border border-[#243149] text-xs font-mono text-[#51DCC8]"
              >
                {formatSMPTE(currentTime, selectedVideo.fps)}
              </div>

              <div className="absolute top-3 right-3 px-2 py-1 rounded bg-[#080B12]/80 backdrop-blur border border-[#243149] text-[11px] font-mono text-slate-300">
                {selectedVideo.width}x{selectedVideo.height} &middot; {selectedVideo.fps}fps &middot;{" "}
                {selectedVideo.codec}
              </div>

              {activeScene && (
                <div className="absolute bottom-3 left-3 px-2 py-0.5 rounded bg-[#080B12]/80 backdrop-blur border border-[#F4BF69]/40 text-[10px] font-mono text-[#F4BF69]">
                  Scene #{activeScene.scene_index + 1} [{activeScene.start_time.toFixed(1)}s -{" "}
                  {activeScene.end_time.toFixed(1)}s]
                </div>
              )}

              {playerError && (
                <div className="absolute inset-x-4 bottom-4 p-3 rounded bg-rose-950/90 border border-rose-800 text-rose-200 text-xs font-mono">
                  {playerError}
                </div>
              )}
            </div>

            {/* Transport Bar & Scrubber */}
            <div className="p-3 rounded-panel bg-[#111827] border border-[#243149] space-y-2.5">
              {/* Visual Range & Scene Cut Strip */}
              <div className="relative h-2.5 rounded bg-[#0B1019] border border-[#243149] overflow-hidden">
                {(inPoint !== null || outPoint !== null) && effectiveDuration > 0 && (
                  <div
                    data-testid="selection-range-bar"
                    style={{
                      left: `${selectionStartPct}%`,
                      width: `${Math.max(0.5, selectionEndPct - selectionStartPct)}%`,
                    }}
                    className="absolute inset-y-0 bg-[#9B8CFF]/40 border-x border-[#9B8CFF]"
                  />
                )}
                {effectiveDuration > 0 &&
                  scenes.slice(0, 150).map((sc) => (
                    <div
                      key={sc.id}
                      style={{ left: `${(sc.start_time / effectiveDuration) * 100}%` }}
                      className="absolute inset-y-0 w-px bg-[#F4BF69]/40"
                      title={`Scene #${sc.scene_index + 1}: ${sc.start_time.toFixed(1)}s`}
                    />
                  ))}
                {effectiveDuration > 0 && (
                  <div
                    style={{ left: `${Math.min(100, (currentTime / effectiveDuration) * 100)}%` }}
                    className="absolute inset-y-0 w-0.5 bg-[#51DCC8]"
                  />
                )}
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={togglePlay}
                  className="px-3 py-1 rounded-control bg-[#9B8CFF] text-[#080B12] text-xs font-semibold shrink-0"
                >
                  {isPlaying ? "Pause" : "Play"}
                </button>
                <input
                  type="range"
                  aria-label="Timeline Scrubber"
                  min={0}
                  max={effectiveDuration || 1}
                  step={0.01}
                  value={currentTime}
                  onChange={(e) => handleSeek(parseFloat(e.target.value))}
                  className="flex-1 studio-scrubber"
                />
                <span className="text-xs font-mono text-[#F5F7FB] shrink-0">
                  {currentTime.toFixed(2)}s / {effectiveDuration.toFixed(2)}s
                </span>
              </div>

              {/* Precision Step & Speed Controls */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono pt-1 border-t border-[#243149]/50">
                <div className="flex flex-wrap items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handleSeek(0)}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                    title="Restart from 0.00s"
                  >
                    0:00
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSeek(currentTime - 5)}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    -5s
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSeek(currentTime - frameStep)}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                    title="Step backward 1 frame"
                  >
                    -1f
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSeek(currentTime + frameStep)}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                    title="Step forward 1 frame"
                  >
                    +1f
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSeek(currentTime + 5)}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    +5s
                  </button>
                  <button
                    type="button"
                    onClick={() => jumpToAdjacentScene(-1)}
                    disabled={scenes.length === 0}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-[#F4BF69] border border-[#243149] disabled:opacity-40"
                  >
                    Prev Scene
                  </button>
                  <button
                    type="button"
                    onClick={() => jumpToAdjacentScene(1)}
                    disabled={scenes.length === 0}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-[#F4BF69] border border-[#243149] disabled:opacity-40"
                  >
                    Next Scene
                  </button>
                </div>

                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-slate-500">Speed:</span>
                  {[0.5, 1.0, 1.25, 1.5, 2.0].map((rate) => (
                    <button
                      key={rate}
                      type="button"
                      onClick={() => handleSpeedChange(rate)}
                      className={`px-1.5 py-0.5 rounded border ${
                        playbackRate === rate
                          ? "bg-[#9B8CFF] text-[#080B12] border-[#9B8CFF] font-semibold"
                          : "bg-[#0B1019] text-slate-400 border-[#243149] hover:text-white"
                      }`}
                    >
                      {rate}x
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={toggleMute}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    {isMuted ? "Unmute" : "Mute"}
                  </button>
                  <button
                    type="button"
                    onClick={handleFullscreen}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    Fullscreen
                  </button>
                </div>
              </div>

              {/* In / Out Clip Selection Transport */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono pt-1.5 border-t border-[#243149]/50">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setInPoint(Number(currentTime.toFixed(2)))}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    Set In: {inPoint !== null ? `${inPoint.toFixed(2)}s` : "--"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setOutPoint(Number(currentTime.toFixed(2)))}
                    className="px-2 py-0.5 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149]"
                  >
                    Set Out: {outPoint !== null ? `${outPoint.toFixed(2)}s` : "--"}
                  </button>
                  {(inPoint !== null || outPoint !== null) && (
                    <span className="text-[11px] text-[#9B8CFF]">
                      Range:{" "}
                      {Math.max(
                        0,
                        (outPoint ?? effectiveDuration) - (inPoint ?? 0)
                      ).toFixed(2)}
                      s
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={handlePreviewSelection}
                    className="px-2 py-0.5 rounded bg-[#172235] hover:bg-[#232f48] text-[#51DCC8] border border-[#243149]"
                  >
                    {isPreviewingRange ? "Previewing Range..." : "Preview Selection"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setInPoint(null);
                      setOutPoint(null);
                      setIsPreviewingRange(false);
                    }}
                    className="text-[10px] text-slate-500 hover:text-slate-300 underline"
                  >
                    Clear Markers
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    aria-label="Export Lossless MP4 Clip"
                    onClick={() => void handleExportClip()}
                    disabled={exportingClip}
                    className="px-3 py-1 rounded-control bg-[#172235] hover:bg-[#232f48] text-[#F5F7FB] border border-[#243149] disabled:opacity-50"
                  >
                    {exportingClip ? "Exporting MP4 Subclip..." : "Export Lossless MP4 Clip"}
                  </button>
                </div>
              </div>

              <div className="text-[10px] font-mono text-slate-500 flex items-center justify-between flex-wrap gap-2">
                <span>
                  Cut Mode: Stream Copy (`-c copy`, keyframe-aligned) with automatic H.264/AAC fallback
                </span>
                <span>Source media remains strictly read-only</span>
              </div>

              {clipResult && (
                <div className="p-2.5 rounded bg-[#0B1019] border border-emerald-900/50 text-emerald-300 text-xs font-mono flex flex-wrap items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <div>
                      Clip ready: {clipResult.clip_filename} ({clipResult.duration.toFixed(2)}s
                      {clipResult.file_size
                        ? ` · ${(clipResult.file_size / (1024 * 1024)).toFixed(2)} MB`
                        : ""}
                      )
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Requested [{clipResult.start_time.toFixed(2)}s - {clipResult.end_time.toFixed(2)}s] (
                      {(clipResult.end_time - clipResult.start_time).toFixed(2)}s) &middot; Mode:{" "}
                      {clipResult.export_mode === "reencoded_libx264"
                        ? "Re-encoded H.264/AAC"
                        : "Stream Copy (Keyframe-Aligned)"}
                    </div>
                  </div>
                  <a
                    href={getClipDownloadUrl(clipResult.clip_filename)}
                    download
                    className="px-2.5 py-1 rounded bg-emerald-900 text-emerald-200 hover:bg-emerald-800 shrink-0"
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
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h3 className="text-xs font-semibold text-[#F5F7FB] tracking-tight">
                  Multi-Track Intelligence Timeline
                </h3>
                <input
                  type="text"
                  aria-label="Filter transcript segments"
                  value={transcriptFilter}
                  onChange={(e) => setTranscriptFilter(e.target.value)}
                  placeholder="Filter dialogue segments..."
                  className="px-2.5 py-1 rounded bg-[#0B1019] border border-[#243149] text-[11px] font-mono text-white placeholder-slate-500 focus:border-[#9B8CFF] focus:outline-none"
                />
              </div>

              {/* Track 1: Speech Transcript & Subtitles */}
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#51DCC8]" />
                    Speech Transcript &amp; Dialogue
                    {transcript?.model_name ? ` (${transcript.model_name})` : ""}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[10px] text-slate-400" data-testid="timing-mode-badge">
                      {timingSummaryLabel}
                    </span>
                    <span>
                      {filteredSegments.length} / {allSegments.length} segments
                    </span>
                  </div>
                </div>

                {/* Subtitle Export Bar */}
                <div className="flex flex-wrap items-center justify-between gap-2 px-2 py-1.5 rounded bg-[#0B1019] border border-[#243149]/80 text-[11px] font-mono">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-slate-400">Export Subtitles:</span>
                    {(["srt", "vtt", "ass"] as SubtitleExportFormat[]).map((fmt) => (
                      <button
                        key={fmt}
                        type="button"
                        aria-label={`Export ${fmt.toUpperCase()} subtitles`}
                        disabled={allSegments.length === 0 || exportingSubFormat !== null}
                        onClick={() => void handleExportSubtitles(fmt)}
                        className="px-2 py-0.5 rounded bg-[#172235] hover:bg-[#232f48] text-[#F5F7FB] border border-[#243149] disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#9B8CFF]"
                      >
                        {exportingSubFormat === fmt ? `Exporting ${fmt.toUpperCase()}...` : fmt.toUpperCase()}
                      </button>
                    ))}
                    {hasWordTimings && (
                      <label className="inline-flex items-center gap-1 text-[10px] text-[#51DCC8] cursor-pointer ml-1">
                        <input
                          type="checkbox"
                          checked={includeAssKaraoke}
                          onChange={(e) => setIncludeAssKaraoke(e.target.checked)}
                          className="accent-[#51DCC8]"
                        />
                        <span>ASS Karaoke (\k)</span>
                      </label>
                    )}
                  </div>
                  <div className="text-[10px]">
                    {subExportSuccess && (
                      <span role="status" className="text-emerald-300">
                        {subExportSuccess}
                      </span>
                    )}
                    {subExportError && (
                      <span role="alert" className="text-rose-300">
                        {subExportError}
                      </span>
                    )}
                  </div>
                </div>

                <div className="max-h-44 overflow-y-auto space-y-1 p-2 rounded bg-[#0B1019] border border-[#243149]">
                  {filteredSegments.length > 0 ? (
                    filteredSegments.map((seg: any) => {
                      const isActive =
                        currentTime >= seg.start_time && currentTime <= seg.end_time;
                      return (
                        <div
                          key={seg.id}
                          onClick={() => handleSeek(seg.start_time)}
                          className={`p-1.5 rounded cursor-pointer text-xs font-mono transition-colors flex items-start justify-between gap-2 ${
                            isActive
                              ? "bg-[#51DCC8]/20 border border-[#51DCC8] text-white"
                              : "hover:bg-[#172235] text-slate-300"
                          }`}
                        >
                          <span className="pr-2">{seg.text}</span>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span className="text-[10px] text-slate-400">
                              {seg.start_time.toFixed(1)}s - {seg.end_time.toFixed(1)}s
                            </span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setInPoint(Number(seg.start_time.toFixed(2)));
                                setOutPoint(Number(seg.end_time.toFixed(2)));
                                handleSeek(seg.start_time);
                              }}
                              className="px-1.5 py-0.5 rounded bg-[#172235] hover:bg-[#232f48] text-[9px] text-[#9B8CFF] border border-[#243149]"
                              title="Set In/Out to this segment"
                            >
                              Set Range
                            </button>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="py-4 text-center text-xs text-slate-500 font-mono">
                      {allSegments.length > 0
                        ? "No dialogue segments match the current filter."
                        : 'No transcript segments available. Click "+ Attach Subtitles" above to import.'}
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
                    scenes.map((sc) => {
                      const isSceneActive =
                        currentTime >= sc.start_time && currentTime < sc.end_time;
                      return (
                        <div
                          key={sc.id}
                          onClick={() => handleSeek(sc.start_time)}
                          className={`p-1.5 rounded shrink-0 cursor-pointer text-center space-y-1 transition-colors border ${
                            isSceneActive
                              ? "bg-[#172235] border-[#F4BF69] text-white"
                              : "bg-[#0B1019] hover:bg-[#172235] border-[#243149]"
                          }`}
                        >
                          <div className="relative w-24 h-14 bg-black rounded overflow-hidden flex items-center justify-center text-[10px] text-slate-400 font-mono">
                            {sc.thumbnail_path && (
                              <img
                                loading="lazy"
                                src={getSceneThumbnailUrl(selectedVideo.id, sc.scene_index)}
                                alt={`Scene #${sc.scene_index + 1}`}
                                className="absolute inset-0 w-full h-full object-cover opacity-80"
                                onError={(e) => {
                                  (e.currentTarget as HTMLImageElement).style.display = "none";
                                }}
                              />
                            )}
                            <span className="relative z-10 px-1 py-0.5 rounded bg-black/70 text-[10px] font-mono text-slate-200">
                              Scene #{sc.scene_index + 1}
                            </span>
                          </div>
                          <p className="text-[10px] font-mono text-slate-300">
                            {sc.start_time.toFixed(1)}s - {sc.end_time.toFixed(1)}s
                          </p>
                        </div>
                      );
                    })
                  ) : (
                    <div className="py-2 text-xs text-slate-500 font-mono">
                      No scene cuts recorded.
                    </div>
                  )}
                </div>
              </div>

              {/* Track 3: Optical OCR Frame Evidence & Availability */}
              <div className="space-y-1.5 pt-2 border-t border-[#243149]/60" data-testid="ocr-status-panel">
                <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-slate-400">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-[#6BCBFF]" />
                    Optical OCR Frame Evidence
                    {ocrStatus?.engine_name
                      ? ` (${ocrStatus.engine_name}${ocrStatus.engine_version ? `@${ocrStatus.engine_version}` : ""})`
                      : ""}
                  </span>
                  <div className="flex items-center gap-2">
                    {ocrStatus?.version_id && (
                      <span className="text-[10px] text-slate-500">
                        ver:{ocrStatus.version_id.slice(0, 8)}
                      </span>
                    )}
                    <span
                      data-testid="ocr-state-badge"
                      className={`px-2 py-0.5 rounded text-[10px] border ${
                        ocrStatus?.status === "completed_with_text"
                          ? "bg-emerald-950/50 text-emerald-300 border-emerald-800"
                          : ocrStatus?.status === "completed_no_text"
                            ? "bg-slate-900 text-slate-300 border-slate-700"
                            : ocrStatus?.status === "running"
                              ? "bg-cyan-950/50 text-[#6BCBFF] border-cyan-800"
                              : ocrStatus?.status === "failed"
                                ? "bg-rose-950/50 text-rose-300 border-rose-800"
                                : ocrStatus?.status === "engine_unavailable"
                                  ? "bg-amber-950/50 text-[#F4BF69] border-amber-800"
                                  : "bg-[#0B1019] text-slate-400 border-[#243149]"
                      }`}
                    >
                      {ocrStatus?.status === "engine_unavailable"
                        ? "OCR Engine Unavailable"
                        : ocrStatus?.status === "not_processed"
                          ? "OCR Not Processed"
                          : ocrStatus?.status === "running"
                            ? "OCR Running"
                            : ocrStatus?.status === "completed_no_text"
                              ? "Completed — No Text Detected"
                              : ocrStatus?.status === "completed_with_text"
                                ? `Completed — ${ocrStatus.extracted_count} Frame(s)`
                                : ocrStatus?.status === "failed"
                                  ? "OCR Failed"
                                  : "OCR Status Unavailable"}
                    </span>
                  </div>
                </div>

                {ocrStatus?.status === "engine_unavailable" && (
                  <div className="p-2.5 rounded bg-[#0B1019] border border-amber-900/50 text-[11px] font-mono text-amber-200/90">
                    {ocrStatus.remediation_hint ??
                      "Install an optional local OCR engine (rapidocr-onnxruntime or tesseract + pytesseract + Pillow) to enable optical frame OCR."}
                  </div>
                )}

                {ocrStatus?.status === "failed" && (
                  <div
                    role="alert"
                    className="p-2.5 rounded bg-rose-950/40 border border-rose-900 text-[11px] font-mono text-rose-300"
                  >
                    OCR stage failed: {ocrStatus.error_message ?? "Unknown OCR error"}
                  </div>
                )}

                {ocrStatus?.status === "not_processed" && (
                  <div className="p-2 rounded bg-[#0B1019] border border-[#243149] text-[11px] font-mono text-slate-400">
                    Local OCR engine is ready. Run the 7-stage pipeline to scan sampled scene keyframes.
                  </div>
                )}

                {ocrStatus?.status === "completed_no_text" && (
                  <div className="p-2 rounded bg-[#0B1019] border border-[#243149] text-[11px] font-mono text-slate-400">
                    Optical OCR ran cleanly on sampled keyframes and detected no on-screen text.
                  </div>
                )}

                {ocrStatus?.status === "completed_with_text" && ocrStatus.frames.length > 0 && (
                  <div className="max-h-36 overflow-y-auto space-y-1 p-2 rounded bg-[#0B1019] border border-[#243149]">
                    {ocrStatus.frames.map((frame) => (
                      <button
                        key={`${frame.scene_index}-${frame.timestamp_sec}`}
                        type="button"
                        onClick={() => handleSeek(frame.timestamp_sec)}
                        aria-label={`Seek to OCR frame at ${frame.timestamp_sec.toFixed(1)}s`}
                        className="w-full text-left p-1.5 rounded hover:bg-[#172235] text-xs font-mono text-slate-200 flex items-start justify-between gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#9B8CFF]"
                      >
                        <span className="pr-2">{frame.text}</span>
                        <span className="text-[10px] text-[#6BCBFF] shrink-0">
                          Scene #{frame.scene_index + 1} · {frame.timestamp_sec.toFixed(1)}s
                        </span>
                      </button>
                    ))}
                  </div>
                )}
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
                  <dt className="text-slate-500">Resolution</dt>
                  <dd className="text-slate-200 mt-0.5">
                    {selectedVideo.width}x{selectedVideo.height}
                  </dd>
                </div>
                <div className="p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">Frame Rate</dt>
                  <dd className="text-slate-200 mt-0.5">{selectedVideo.fps} fps</dd>
                </div>
                <div className="p-2 rounded bg-[#0B1019] border border-[#243149]">
                  <dt className="text-slate-500">Duration</dt>
                  <dd className="text-slate-200 mt-0.5">{selectedVideo.duration.toFixed(2)}s</dd>
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
              <div className="p-4 rounded-panel bg-[#111827] border border-[#9B8CFF]/40 space-y-2.5">
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
                {summary.chapters?.length > 0 && (
                  <div className="pt-2 border-t border-[#243149] space-y-1">
                    <span className="text-[10px] font-mono text-slate-400">
                      Chapter Markers (click to seek):
                    </span>
                    {summary.chapters.map((ch, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSeek(ch.start_time)}
                        className="w-full text-left px-2 py-1 rounded bg-[#0B1019] hover:bg-[#172235] border border-[#243149] text-[11px] font-mono flex items-center justify-between"
                      >
                        <span className="text-slate-200 truncate pr-2">{ch.title}</span>
                        <span className="text-[#51DCC8] shrink-0">{ch.start_time.toFixed(1)}s</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Timecode Annotations & Notes */}
            <div className="p-4 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
              <h3 className="text-xs font-semibold text-[#F5F7FB]">Annotations &amp; Notes</h3>

              <form onSubmit={(e) => void handleCreateAnnotation(e)} className="space-y-2">
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
                &times;
              </button>
            </div>

            {subMsg && (
              <div className="p-2 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8]">
                {subMsg}
              </div>
            )}

            <form onSubmit={(e) => void handleAttachSubtitles(e)} className="space-y-3">
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

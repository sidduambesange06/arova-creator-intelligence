import { useEffect, useState } from "react";
import {
  fetchJobs,
  fetchMediaLibraryStats,
  fetchVideos,
  importVideos,
  uploadVideoSubtitles,
  type MediaLibraryStats,
  type ProcessingJob,
  type VideoItem,
} from "../../services/api";

interface OverviewViewProps {
  onNavigate: (section: string) => void;
  onSelectVideo?: (videoId: string) => void;
}

export function OverviewView({ onNavigate, onSelectVideo }: OverviewViewProps) {
  const [stats, setStats] = useState<MediaLibraryStats | null>(null);
  const [recentVideos, setRecentVideos] = useState<VideoItem[]>([]);
  const [recentJobs, setRecentJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ingest Modal State
  const [showModal, setShowModal] = useState(false);
  const [modalTab, setModalTab] = useState<"media" | "subtitles">("media");
  const [importPath, setImportPath] = useState("");
  const [importing, setImporting] = useState(false);
  const [importFeedback, setImportFeedback] = useState<string | null>(null);

  // Subtitle Ingest State
  const [selectedVideoId, setSelectedVideoId] = useState("");
  const [subtitleFilename, setSubtitleFilename] = useState("subtitles.srt");
  const [subtitleLanguage, setSubtitleLanguage] = useState("en");
  const [subtitleContent, setSubtitleContent] = useState("");
  const [submittingSubtitle, setSubmittingSubtitle] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [statsData, vids, jobs] = await Promise.all([
          fetchMediaLibraryStats().catch(() => null),
          fetchVideos().catch(() => []),
          fetchJobs().catch(() => []),
        ]);
        if (!cancelled) {
          setStats(statsData);
          setRecentVideos(vids);
          if (vids.length > 0 && !selectedVideoId) {
            setSelectedVideoId(vids[0].id);
          }
          setRecentJobs(jobs);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load dashboard data");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleImportMedia(e: React.FormEvent) {
    e.preventDefault();
    if (!importPath.trim()) return;
    setImporting(true);
    setImportFeedback(null);
    try {
      const res = await importVideos(importPath.trim());
      setImportFeedback(
        `Imported ${res.imported.length} video(s). Skipped duplicates: ${res.skipped_duplicates}.`
      );
      setImportPath("");
      const [newStats, vids] = await Promise.all([
        fetchMediaLibraryStats().catch(() => null),
        fetchVideos().catch(() => []),
      ]);
      setStats(newStats);
      setRecentVideos(vids);
    } catch (err) {
      setImportFeedback(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  async function handleUploadSubtitles(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedVideoId || !subtitleContent.trim()) return;
    setSubmittingSubtitle(true);
    setImportFeedback(null);
    try {
      await uploadVideoSubtitles(
        selectedVideoId,
        subtitleContent.trim(),
        subtitleFilename.trim() || "subtitles.srt",
        subtitleLanguage.trim() || "en"
      );
      setImportFeedback(`Subtitles imported successfully for video ${selectedVideoId}!`);
      setSubtitleContent("");
    } catch (err) {
      setImportFeedback(err instanceof Error ? err.message : "Subtitle import failed");
    } finally {
      setSubmittingSubtitle(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Hero Cockpit */}
      <div className="p-6 rounded-panel bg-[#111827] border border-[#243149] space-y-4 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30">
                LOCAL ENCLAVE ACTIVE
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
                ZERO EGRESS GUARANTEE
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-semibold text-[#F5F7FB] tracking-tight">
              Your media, understood.
            </h1>
            <p className="text-xs text-[#A2AEC0] max-w-2xl leading-relaxed">
              Fully indexed on local hardware. Zero cloud egress. Frame-accurate semantic retrieval
              across speech, visual keyframes, and multi-track intelligence.
            </p>
            {error && (
              <p className="text-[11px] font-mono text-[#FF7386]">{error}</p>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setShowModal(true)}
              className="px-4 py-2 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-sans transition-colors shadow-sm flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
              </svg>
              Index Local Media
            </button>
            <button
              type="button"
              onClick={() => onNavigate("hybrid-search")}
              className="px-3.5 py-2 rounded-control bg-[#172235] hover:bg-[#232f48] text-[#F5F7FB] text-xs font-medium border border-[#243149] transition-colors"
            >
              Ask Archive
            </button>
          </div>
        </div>

        {/* Quick Query Shortcuts */}
        <div className="pt-2 border-t border-[#243149] flex flex-wrap items-center gap-2 text-xs">
          <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">
            Quick Queries:
          </span>
          {[
            "Where do I discuss privacy and local AI?",
            "Find scenes with high visual motion",
            "Summarize the latest indexed video",
          ].map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onNavigate("hybrid-search")}
              className="px-2.5 py-1 rounded bg-[#0B1019] hover:bg-[#172235] text-slate-300 border border-[#243149] text-[11px] font-mono transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* 6 Key Metrics Matrix */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3.5 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between">
          <span className="text-[11px] font-mono text-slate-400">Total Videos</span>
          <span className="text-xl font-bold font-mono text-[#F5F7FB] mt-1">
            {stats ? stats.total_videos : loading ? "â€¦" : "0"}
          </span>
          <span className="text-[10px] text-slate-500 font-mono mt-1">Indexed files</span>
        </div>

        <div className="p-3.5 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between">
          <span className="text-[11px] font-mono text-slate-400">Total Duration</span>
          <span className="text-xl font-bold font-mono text-[#9B8CFF] mt-1">
            {stats ? `${stats.total_duration_sec.toFixed(1)}s` : loading ? "â€¦" : "0s"}
          </span>
          <span className="text-[10px] text-slate-500 font-mono mt-1">Playable runtime</span>
        </div>

        <div className="p-3.5 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between">
          <span className="text-[11px] font-mono text-slate-400">Transcripts</span>
          <span className="text-xl font-bold font-mono text-[#51DCC8] mt-1">
            {stats ? stats.total_transcripts_indexed : loading ? "â€¦" : "0"}
          </span>
          <span className="text-[10px] text-slate-500 font-mono mt-1">ASR / Subtitles</span>
        </div>

        <div className="p-3.5 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between">
          <span className="text-[11px] font-mono text-slate-400">Scene Cuts</span>
          <span className="text-xl font-bold font-mono text-[#F4BF69] mt-1">
            {stats ? stats.total_scene_cuts : loading ? "â€¦" : "0"}
          </span>
          <span className="text-[10px] text-slate-500 font-mono mt-1">Visual segments</span>
        </div>

        <div className="p-3.5 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between">
          <span className="text-[11px] font-mono text-slate-400">Collections</span>
          <span className="text-xl font-bold font-mono text-[#6BCBFF] mt-1">
            {stats ? stats.total_collections : loading ? "â€¦" : "0"}
          </span>
          <span className="text-[10px] text-slate-500 font-mono mt-1">Organized bins</span>
        </div>

        <div className="p-3.5 rounded-panel bg-[#111827] border border-[#243149] flex flex-col justify-between">
          <span className="text-[11px] font-mono text-slate-400">Active Pipeline</span>
          <span className="text-xl font-bold font-mono text-emerald-400 mt-1">
            {recentJobs.filter((j) => j.status === "running").length}
          </span>
          <span className="text-[10px] text-slate-500 font-mono mt-1">Running jobs</span>
        </div>
      </div>

      {/* Two Column Layout: Recent Media & Active DAG Jobs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Indexed Media */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <h2 className="text-sm font-semibold text-[#F5F7FB]">Recent Media Assets</h2>
            <button
              type="button"
              onClick={() => onNavigate("media-library")}
              className="text-xs font-mono text-[#9B8CFF] hover:underline"
            >
              View All ({recentVideos.length}) â†’
            </button>
          </div>

          {recentVideos.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 font-mono">
              No videos indexed yet. Click &quot;Index Local Media&quot; above to begin.
            </div>
          ) : (
            <div className="space-y-2">
              {recentVideos.slice(0, 5).map((vid) => (
                <div
                  key={vid.id}
                  onClick={() => {
                    onSelectVideo?.(vid.id);
                    onNavigate("media-library");
                  }}
                  className="p-2.5 rounded-control bg-[#0B1019] hover:bg-[#172235] border border-[#243149] flex items-center justify-between cursor-pointer transition-colors"
                >
                  <div className="min-w-0 pr-3">
                    <p className="text-xs font-medium text-[#F5F7FB] truncate">{vid.filename}</p>
                    <p className="text-[10px] font-mono text-slate-400 mt-0.5">
                      {vid.duration.toFixed(1)}s Â· {vid.width}x{vid.height} Â· {vid.codec}
                    </p>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-[#51DCC8] border border-[#51DCC8]/30 shrink-0">
                    {vid.processing_status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Resumable DAG Pipeline Activity */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <h2 className="text-sm font-semibold text-[#F5F7FB]">DAG Pipeline Activity</h2>
            <button
              type="button"
              onClick={() => onNavigate("processing-jobs")}
              className="text-xs font-mono text-[#9B8CFF] hover:underline"
            >
              All Jobs ({recentJobs.length}) â†’
            </button>
          </div>

          {recentJobs.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 font-mono">
              No background processing jobs recorded yet.
            </div>
          ) : (
            <div className="space-y-2">
              {recentJobs.slice(0, 5).map((job) => (
                <div
                  key={job.id}
                  className="p-2.5 rounded-control bg-[#0B1019] border border-[#243149] space-y-1.5"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-[#F5F7FB] truncate max-w-[200px]">
                      Job: {job.id.slice(0, 8)}â€¦
                    </span>
                    <span
                      className={`text-[10px] font-mono px-1.5 py-0.5 rounded uppercase ${
                        job.status === "completed"
                          ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800"
                          : job.status === "running"
                          ? "bg-amber-950/60 text-amber-400 border border-amber-800 animate-pulse"
                          : job.status === "failed"
                          ? "bg-rose-950/60 text-rose-400 border border-rose-800"
                          : "bg-slate-800 text-slate-300"
                      }`}
                    >
                      {job.status}
                    </span>
                  </div>
                  <div className="w-full bg-[#172235] rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-[#9B8CFF] h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${Math.round(job.progress * 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <span>{job.job_type}</span>
                    <span>{Math.round(job.progress * 100)}% complete</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Index Media & Subtitle Import Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-[#111827] border border-[#243149] rounded-panel p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#243149] pb-3">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setModalTab("media")}
                  className={`text-xs font-semibold px-2.5 py-1 rounded ${
                    modalTab === "media"
                      ? "bg-[#9B8CFF] text-[#080B12]"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Index Media File / Folder
                </button>
                <button
                  type="button"
                  onClick={() => setModalTab("subtitles")}
                  className={`text-xs font-semibold px-2.5 py-1 rounded ${
                    modalTab === "subtitles"
                      ? "bg-[#9B8CFF] text-[#080B12]"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Attach Sidecar Subtitles (.srt / .vtt)
                </button>
              </div>
              <button
                type="button"
                onClick={() => {
                  setShowModal(false);
                  setImportFeedback(null);
                }}
                className="text-slate-400 hover:text-white text-sm"
              >
                âœ•
              </button>
            </div>

            {importFeedback && (
              <div className="p-2.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8]">
                {importFeedback}
              </div>
            )}

            {modalTab === "media" ? (
              <form onSubmit={handleImportMedia} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-slate-300 font-medium">
                    Local video file or folder path:
                  </label>
                  <input
                    type="text"
                    required
                    value={importPath}
                    onChange={(e) => setImportPath(e.target.value)}
                    placeholder="e.g. C:/videos/sample.mp4 or ./data/raw_media"
                    className="w-full px-3 py-2 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-[#F5F7FB] font-mono focus:border-[#9B8CFF] focus:outline-none"
                  />
                  <p className="text-[11px] text-slate-500 font-mono">
                    Must reside within approved ALLOWED_MEDIA_ROOTS. Source files are strictly read-only.
                  </p>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-3 py-1.5 rounded-control bg-[#172235] text-xs text-slate-300 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={importing}
                    className="px-4 py-1.5 rounded-control bg-[#9B8CFF] text-xs font-semibold text-[#080B12] disabled:opacity-50"
                  >
                    {importing ? "Scanning & Importing..." : "Start Ingest"}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleUploadSubtitles} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs text-slate-300 font-medium">Select Target Video:</label>
                  <select
                    value={selectedVideoId}
                    onChange={(e) => setSelectedVideoId(e.target.value)}
                    className="w-full px-3 py-2 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-[#F5F7FB] font-mono focus:border-[#9B8CFF] focus:outline-none"
                  >
                    {recentVideos.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.filename} ({v.duration.toFixed(1)}s)
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-slate-300 font-medium">Filename / Format:</label>
                    <input
                      type="text"
                      value={subtitleFilename}
                      onChange={(e) => setSubtitleFilename(e.target.value)}
                      placeholder="subtitles.srt"
                      className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-[#F5F7FB] font-mono"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-slate-300 font-medium">Language:</label>
                    <input
                      type="text"
                      value={subtitleLanguage}
                      onChange={(e) => setSubtitleLanguage(e.target.value)}
                      placeholder="en, hi, kn, etc."
                      className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-[#F5F7FB] font-mono"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-slate-300 font-medium">
                    SRT or WebVTT Content:
                  </label>
                  <textarea
                    rows={6}
                    required
                    value={subtitleContent}
                    onChange={(e) => setSubtitleContent(e.target.value)}
                    placeholder={"1\n00:00:00,000 --> 00:00:04,500\nDialogue line here..."}
                    className="w-full px-3 py-2 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-[#F5F7FB] font-mono focus:border-[#9B8CFF] focus:outline-none"
                  />
                  <p className="text-[11px] text-slate-500 font-mono">
                    Works offline without running local ASR models. Instantly populates transcript search.
                  </p>
                </div>

                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="px-3 py-1.5 rounded-control bg-[#172235] text-xs text-slate-300 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submittingSubtitle || !selectedVideoId}
                    className="px-4 py-1.5 rounded-control bg-[#51DCC8] text-xs font-semibold text-[#080B12] disabled:opacity-50"
                  >
                    {submittingSubtitle ? "Ingesting..." : "Attach Subtitles"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

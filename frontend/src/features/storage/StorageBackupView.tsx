import { useEffect, useState } from "react";
import {
  dryRunPortableImport,
  exportPortableArchive,
  fetchDuplicateMedia,
  fetchMediaAvailability,
  fetchVideos,
  getArchiveDownloadUrl,
  importPortableArchive,
  relinkMediaAsset,
  uploadPortableArchive,
  type DuplicateGroup,
  type ExportSummary,
  type ImportDryRunReport,
  type ImportResult,
  type MediaAvailability,
  type VideoItem,
} from "../../services/api";

export function StorageBackupView() {
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [duplicates, setDuplicates] = useState<DuplicateGroup[]>([]);
  const [feedback, setFeedback] = useState<string | null>(null);

  // Export State
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [includeArtifacts, setIncludeArtifacts] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportSummary, setExportSummary] = useState<ExportSummary | null>(null);

  // Import State
  const [importPath, setImportPath] = useState("");
  const [uploadingFile, setUploadingFile] = useState(false);
  const [dryRunReport, setDryRunReport] = useState<ImportDryRunReport | null>(null);
  const [dryRunning, setDryRunning] = useState(false);
  const [conflictPolicy, setConflictPolicy] = useState("skip");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  // Availability & Relinking State
  const [checkVersionId, setCheckVersionId] = useState("");
  const [availability, setAvailability] = useState<MediaAvailability | null>(null);
  const [checkingAvail, setCheckingAvail] = useState(false);
  const [newFilePath, setNewFilePath] = useState("");
  const [relinking, setRelinking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadInitial() {
      try {
        const [vids, dups] = await Promise.all([
          fetchVideos().catch(() => []),
          fetchDuplicateMedia().catch(() => []),
        ]);
        if (!cancelled) {
          setVideos(vids);
          setDuplicates(dups);
          if (vids.length > 0) {
            setCheckVersionId(vids[0].id);
          }
        }
      } catch {
        // Handled
      }
    }
    void loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleExport(e: React.FormEvent) {
    e.preventDefault();
    setExporting(true);
    setExportSummary(null);
    setFeedback(null);
    try {
      const summary = await exportPortableArchive({
        asset_ids: selectedVideoIds.length > 0 ? selectedVideoIds : undefined,
        include_artifacts: includeArtifacts,
      });
      setExportSummary(summary);
      setFeedback(`Export completed: ${summary.archive_name} (${(summary.file_size_bytes / 1024).toFixed(1)} KB)`);

      // Trigger automatic browser download
      const downloadUrl = summary.download_url || getArchiveDownloadUrl(summary.archive_name);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = summary.archive_name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingFile(true);
    setFeedback(null);
    setDryRunReport(null);
    setImportResult(null);
    try {
      const uploaded = await uploadPortableArchive(file);
      setImportPath(uploaded.archive_path);
      setFeedback(`Uploaded archive ${uploaded.filename}. Validating archive manifest...`);
      // Automatically preview the uploaded archive
      const report = await dryRunPortableImport(uploaded.archive_path);
      setDryRunReport(report);
      setFeedback(`Archive verified: ${report.total_entries} entries found.`);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Archive upload or preview failed");
    } finally {
      setUploadingFile(false);
    }
  }

  async function handleDryRun(e: React.FormEvent) {
    e.preventDefault();
    if (!importPath.trim()) return;
    setDryRunning(true);
    setDryRunReport(null);
    setImportResult(null);
    setFeedback(null);
    try {
      const report = await dryRunPortableImport(importPath.trim());
      setDryRunReport(report);
      setFeedback(`Dry-run validation finished: ${report.valid ? "Valid container" : "Invalid container"}`);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Dry-run preview failed");
    } finally {
      setDryRunning(false);
    }
  }

  async function handleExecuteImport() {
    if (!importPath.trim()) return;
    setImporting(true);
    setFeedback(null);
    try {
      const res = await importPortableArchive(importPath.trim(), conflictPolicy);
      setImportResult(res);
      setFeedback(`Import completed with status: ${res.status}. Remapped: ${res.remapped_count} record(s).`);
      const updatedVids = await fetchVideos().catch(() => []);
      setVideos(updatedVids);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  async function handleCheckAvailability() {
    if (!checkVersionId.trim()) return;
    setCheckingAvail(true);
    setAvailability(null);
    try {
      const avail = await fetchMediaAvailability(checkVersionId.trim());
      setAvailability(avail);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Availability check failed");
    } finally {
      setCheckingAvail(false);
    }
  }

  async function handleRelink(e: React.FormEvent) {
    e.preventDefault();
    if (!checkVersionId.trim() || !newFilePath.trim()) return;
    setRelinking(true);
    try {
      const res = await relinkMediaAsset(checkVersionId.trim(), newFilePath.trim());
      setFeedback(`Relink successful: ${res.message}`);
      setNewFilePath("");
      void handleCheckAvailability();
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Relink failed");
    } finally {
      setRelinking(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header Stance */}
      <div className="p-6 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#9B8CFF]/10 text-[#9B8CFF] border border-[#9B8CFF]/30 font-semibold">
            PORTABLE MEDIA MEMORY (.AROVA)
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30 font-semibold">
            SHA-256 TAMPER-EVIDENT ARCHIVES
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
            ZERO VENDOR LOCK-IN
          </span>
        </div>
        <h1 className="text-xl font-semibold text-[#F5F7FB]">
          Storage, Backup &amp; Portable Media Memory
        </h1>
        <p className="text-xs text-[#A2AEC0] max-w-4xl leading-relaxed">
          Export your complete video library intelligence (transcripts, scene cuts, embeddings, and human annotations)
          into a single, self-contained <code className="text-[#9B8CFF] font-mono">.arova</code> archive.
          Move your creator memory between laptops, backup to external drives, or share datasets with AI agents without cloud dependency.
        </p>

        {feedback && (
          <div className="p-3 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8] flex items-center justify-between">
            <span>{feedback}</span>
            <button
              type="button"
              onClick={() => setFeedback(null)}
              className="text-slate-500 hover:text-white"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Main Grid: Export Wizard and Import Engine */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Export .arova Wizard */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F5F7FB]">Export Portable Archive (.arova)</h2>
              <p className="text-[11px] text-slate-400">Bundle metadata, transcripts, and embeddings</p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
              Format v1.0.0
            </span>
          </div>

          <form onSubmit={handleExport} className="space-y-4 font-sans">
            <div className="space-y-1.5">
              <label className="text-xs text-slate-300 font-medium">Select Videos to Include:</label>
              <div className="max-h-40 overflow-y-auto p-2.5 rounded bg-[#0B1019] border border-[#243149] space-y-1.5">
                {videos.length === 0 ? (
                  <p className="text-xs font-mono text-slate-500 py-2 text-center">
                    No videos indexed yet. Export will create empty container.
                  </p>
                ) : (
                  videos.map((v) => (
                    <label key={v.id} className="flex items-center gap-2.5 text-xs font-mono text-slate-300 hover:text-white cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedVideoIds.includes(v.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedVideoIds((prev) => [...prev, v.id]);
                          } else {
                            setSelectedVideoIds((prev) => prev.filter((id) => id !== v.id));
                          }
                        }}
                        className="rounded bg-[#172235] border-[#243149] text-[#9B8CFF]"
                      />
                      <span className="truncate flex-1">{v.filename}</span>
                      <span className="text-[10px] text-slate-500 shrink-0">({v.duration.toFixed(1)}s)</span>
                    </label>
                  ))
                )}
              </div>
              <p className="text-[10px] text-slate-500 font-mono">
                {selectedVideoIds.length === 0
                  ? "All videos in library will be included in the archive."
                  : `${selectedVideoIds.length} video(s) specifically selected.`}
              </p>
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={includeArtifacts}
                onChange={(e) => setIncludeArtifacts(e.target.checked)}
                className="rounded bg-[#0B1019] border-[#243149] text-[#9B8CFF]"
              />
              <span>Include versioned artifacts (transcripts, OCR text, scene cuts, embeddings)</span>
            </label>

            <button
              type="submit"
              disabled={exporting}
              className="w-full py-2.5 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50 transition-colors shadow-sm flex items-center justify-center gap-2"
            >
              {exporting ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-[#080B12]" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Streaming Portable Archive...</span>
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  <span>Export &amp; Download .arova Bundle</span>
                </>
              )}
            </button>
          </form>

          {/* Export Success Card with Direct Download CTA */}
          {exportSummary && (
            <div className="p-4 rounded bg-[#0B1019] border border-emerald-900/50 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between">
                <div className="text-[#51DCC8] font-semibold flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-[#51DCC8]" />
                  Archive Generated Successfully
                </div>
                <span className="text-[10px] text-slate-500">v{exportSummary.format_version}</span>
              </div>
              <div className="space-y-1 text-slate-300">
                <p><span className="text-slate-500">File:</span> {exportSummary.archive_name}</p>
                <p><span className="text-slate-500">Size:</span> {(exportSummary.file_size_bytes / 1024).toFixed(1)} KB</p>
                <p className="text-[10px] text-slate-400 break-all">
                  <span className="text-slate-500">SHA-256:</span> {exportSummary.sha256}
                </p>
              </div>
              <div className="pt-2 border-t border-[#243149]">
                <a
                  href={exportSummary.download_url || getArchiveDownloadUrl(exportSummary.archive_name)}
                  download={exportSummary.archive_name}
                  className="w-full py-2 rounded-control bg-[#51DCC8] hover:bg-[#43c4b2] text-[#080B12] text-xs font-semibold font-mono text-center transition-colors shadow-sm flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  <span>Download .arova Archive File</span>
                </a>
              </div>
            </div>
          )}
        </div>

        {/* Import .arova with Dry-Run Preview */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F5F7FB]">Import Portable Archive</h2>
              <p className="text-[11px] text-slate-400">Restore or merge media memory archives</p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
              Dry-Run Gated
            </span>
          </div>

          {/* Option A: Browser File Upload */}
          <div className="space-y-1.5">
            <label className="text-xs text-slate-300 font-medium">Select .arova file from your computer:</label>
            <div className="flex items-center gap-2">
              <label className="flex-1 px-3 py-2 rounded bg-[#0B1019] border border-[#243149] border-dashed hover:border-[#9B8CFF] cursor-pointer text-xs font-mono text-slate-400 hover:text-white transition-colors text-center">
                <input
                  type="file"
                  accept=".arova,.zip"
                  onChange={handleFileUpload}
                  disabled={uploadingFile}
                  className="hidden"
                />
                {uploadingFile ? "Uploading and verifying archive..." : "Choose .arova file..."}
              </label>
            </div>
          </div>

          <div className="flex items-center gap-2 text-slate-600 text-xs font-mono">
            <span className="flex-1 border-t border-[#243149]" />
            <span>OR ENTER SERVER PATH</span>
            <span className="flex-1 border-t border-[#243149]" />
          </div>

          {/* Option B: Direct Path Input */}
          <form onSubmit={handleDryRun} className="space-y-3 font-sans">
            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Filesystem Path:</label>
              <input
                type="text"
                value={importPath}
                onChange={(e) => setImportPath(e.target.value)}
                placeholder="e.g. C:/exports/my_archive.arova"
                className="w-full px-3 py-2 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={dryRunning || !importPath.trim()}
              className="w-full py-2 rounded bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-slate-200 border border-[#243149] transition-colors disabled:opacity-50"
            >
              {dryRunning ? "Analyzing Container..." : "1. Dry-Run Preview"}
            </button>
          </form>

          {/* Dry Run Report */}
          {dryRunReport && (
            <div className="p-4 rounded bg-[#0B1019] border border-[#243149] space-y-2.5 text-xs font-mono">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[#F5F7FB]">Dry-Run Inspection Report:</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                    dryRunReport.valid ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-rose-950 text-rose-300 border border-rose-800"
                  }`}
                >
                  {dryRunReport.valid ? "VALID ARCHIVE" : "REJECTED"}
                </span>
              </div>
              <p className="text-slate-400">Total Entries: {dryRunReport.total_entries}</p>
              <p className="text-slate-400">Duplicate Conflicts: {dryRunReport.duplicate_conflicts}</p>

              <div className="flex items-center gap-2 pt-3 border-t border-[#243149]">
                <label className="text-[11px] text-slate-400 font-mono">Conflict Policy:</label>
                <select
                  value={conflictPolicy}
                  onChange={(e) => setConflictPolicy(e.target.value)}
                  className="px-2.5 py-1.5 rounded bg-[#111827] border border-[#243149] text-xs text-white font-mono focus:outline-none"
                >
                  <option value="skip">skip existing</option>
                  <option value="overwrite">overwrite existing</option>
                  <option value="rename">rename with alias</option>
                </select>
                <button
                  type="button"
                  onClick={handleExecuteImport}
                  disabled={importing || !dryRunReport.valid}
                  className="flex-1 py-1.5 rounded bg-[#51DCC8] hover:bg-[#43c4b2] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50 transition-colors"
                >
                  {importing ? "Importing Records..." : "2. Commit Import"}
                </button>
              </div>
            </div>
          )}

          {importResult && (
            <div className="p-3.5 rounded bg-[#0B1019] border border-emerald-900/50 text-xs font-mono text-emerald-300">
              Import Result: {importResult.status.toUpperCase()}. Remapped records: {importResult.remapped_count}.
            </div>
          )}
        </div>
      </div>

      {/* Two Column Layout: Availability & Relinking vs Duplicate Media */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Availability & Relinking */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F5F7FB]">Physical Media Availability &amp; Relinking</h2>
              <p className="text-[11px] text-slate-400">Check if media files exist at their registered paths</p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
              Integrity Probe
            </span>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={checkVersionId}
              onChange={(e) => setCheckVersionId(e.target.value)}
              placeholder="Enter Version or Video ID..."
              className="flex-1 px-3 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:outline-none"
            />
            <button
              type="button"
              onClick={handleCheckAvailability}
              disabled={checkingAvail}
              className="px-3.5 py-1.5 rounded bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-white border border-[#243149] transition-colors"
            >
              Check
            </button>
          </div>

          {availability && (
            <div className="p-3.5 rounded bg-[#0B1019] border border-[#243149] space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Status:</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] uppercase font-semibold ${
                    availability.availability === "available"
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                      : "bg-rose-950 text-rose-300 border border-rose-800"
                  }`}
                >
                  {availability.availability}
                </span>
              </div>
              <p className="text-slate-300 truncate">Path: {availability.file_path || "None registered"}</p>
              <div className="flex gap-4 text-slate-400 text-[11px]">
                <span>Playable: {availability.can_play ? "YES" : "NO"}</span>
                <span>Exportable: {availability.can_export ? "YES" : "NO"}</span>
              </div>

              {/* Relink Form if unavailable */}
              {availability.availability !== "available" && (
                <form onSubmit={handleRelink} className="pt-2 border-t border-[#243149] space-y-2">
                  <label className="text-[11px] text-slate-300 font-medium">Relink to new file path:</label>
                  <input
                    type="text"
                    required
                    value={newFilePath}
                    onChange={(e) => setNewFilePath(e.target.value)}
                    placeholder="C:/new_path/video.mp4"
                    className="w-full px-2.5 py-1.5 rounded bg-[#111827] border border-[#243149] text-xs text-white font-mono focus:outline-none"
                  />
                  <button
                    type="submit"
                    disabled={relinking}
                    className="w-full py-1.5 rounded bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono transition-colors"
                  >
                    {relinking ? "Relinking..." : "Relink File Asset"}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>

        {/* Duplicate Media Detector */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3 shadow-sm">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F5F7FB]">
                Duplicate Media Groups ({duplicates.length})
              </h2>
              <p className="text-[11px] text-slate-400">Identical video files discovered across library roots</p>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
              SHA-256 Match
            </span>
          </div>

          {duplicates.length === 0 ? (
            <div className="py-10 text-center text-xs text-slate-400 font-mono">
              Zero duplicate video files detected across library roots.
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {duplicates.map((dup) => (
                <div
                  key={dup.sha256}
                  className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-1.5 text-xs font-mono"
                >
                  <div className="flex items-center justify-between text-[#9B8CFF]">
                    <span className="truncate max-w-[200px]">Hash: {dup.sha256.slice(0, 16)}…</span>
                    <span className="text-slate-400 text-[11px]">{dup.locations_count} locations</span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    {dup.locations.map((loc) => (
                      <div key={loc.location_id} className="truncate text-slate-300">
                        • {loc.rel_path} ({loc.availability})
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default StorageBackupView;

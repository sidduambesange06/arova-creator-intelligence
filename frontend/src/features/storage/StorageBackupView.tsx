import { useEffect, useState } from "react";
import {
  dryRunPortableImport,
  exportPortableArchive,
  fetchDuplicateMedia,
  fetchMediaAvailability,
  fetchVideos,
  importPortableArchive,
  relinkMediaAsset,
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
      setFeedback(`Export generated: ${summary.archive_name} (${(summary.file_size_bytes / 1024).toFixed(1)} KB)`);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
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
      setFeedback(`Import completed with status: ${res.status}`);
      // Refresh videos
      const updatedVids = await fetchVideos();
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
      {/* Header */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#9B8CFF]/10 text-[#9B8CFF] border border-[#9B8CFF]/30">
            TASK-4D PORTABLE MEDIA MEMORY
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
            .AROVA ARCHIVES
          </span>
        </div>
        <h1 className="text-lg font-semibold text-[#F5F7FB]">
          Storage, Backup &amp; Portable Media Memory
        </h1>
        <p className="text-xs text-[#A2AEC0]">
          Export complete intelligence bundles (.arova), inspect archives with dry-run previews,
          detect duplicates by SHA-256, and relink missing media.
        </p>

        {feedback && (
          <div className="p-2 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8]">
            {feedback}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Export .arova Wizard */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">Export Portable Archive (.arova)</h2>
          <form onSubmit={handleExport} className="space-y-3 font-sans">
            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Select Videos to Include:</label>
              <div className="max-h-36 overflow-y-auto p-2 rounded bg-[#0B1019] border border-[#243149] space-y-1">
                {videos.map((v) => (
                  <label key={v.id} className="flex items-center gap-2 text-xs font-mono text-slate-300">
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
                      className="rounded bg-[#172235] border-[#243149]"
                    />
                    <span className="truncate">{v.filename} ({v.duration.toFixed(1)}s)</span>
                  </label>
                ))}
              </div>
              <p className="text-[10px] text-slate-500 font-mono">
                Leave unselected to export entire library memory.
              </p>
            </div>

            <label className="flex items-center gap-2 text-xs text-slate-300">
              <input
                type="checkbox"
                checked={includeArtifacts}
                onChange={(e) => setIncludeArtifacts(e.target.checked)}
                className="rounded bg-[#0B1019] border-[#243149]"
              />
              <span>Include versioned artifacts (transcripts, embeddings, scene metadata)</span>
            </label>

            <button
              type="submit"
              disabled={exporting}
              className="w-full py-2 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50"
            >
              {exporting ? "Generating Bundle..." : "Export .arova Bundle"}
            </button>
          </form>

          {exportSummary && (
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-1.5 text-xs font-mono">
              <div className="text-[#51DCC8] font-semibold">Archive Generated Successfully</div>
              <p className="text-slate-300">File: {exportSummary.archive_name}</p>
              <p className="text-slate-400">Size: {(exportSummary.file_size_bytes / 1024).toFixed(1)} KB</p>
              <p className="text-slate-500 text-[10px] break-all">SHA-256: {exportSummary.sha256}</p>
            </div>
          )}
        </div>

        {/* Import .arova with Dry-Run Preview */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">Import Portable Archive</h2>
          <form onSubmit={handleDryRun} className="space-y-3 font-sans">
            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Archive Path (.arova / .zip):</label>
              <input
                type="text"
                required
                value={importPath}
                onChange={(e) => setImportPath(e.target.value)}
                placeholder="e.g. C:/exports/my_archive.arova"
                className="w-full px-3 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
              />
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={dryRunning || !importPath.trim()}
                className="flex-1 py-1.5 rounded bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-slate-200 border border-[#243149] disabled:opacity-50"
              >
                {dryRunning ? "Analyzing..." : "1. Dry-Run Preview"}
              </button>
            </div>
          </form>

          {dryRunReport && (
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[#F5F7FB]">Dry-Run Report:</span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[10px] ${
                    dryRunReport.valid ? "bg-emerald-950 text-emerald-300" : "bg-rose-950 text-rose-300"
                  }`}
                >
                  {dryRunReport.valid ? "VALID ARCHIVE" : "INVALID"}
                </span>
              </div>
              <p className="text-slate-400">Total Entries: {dryRunReport.total_entries}</p>
              <p className="text-slate-400">Duplicate Conflicts: {dryRunReport.duplicate_conflicts}</p>

              <div className="flex items-center gap-2 pt-2 border-t border-[#243149]">
                <label className="text-[11px] text-slate-400 font-mono">Conflict Policy:</label>
                <select
                  value={conflictPolicy}
                  onChange={(e) => setConflictPolicy(e.target.value)}
                  className="px-2 py-1 rounded bg-[#111827] border border-[#243149] text-xs text-white font-mono"
                >
                  <option value="skip">skip</option>
                  <option value="overwrite">overwrite</option>
                  <option value="rename">rename</option>
                </select>
                <button
                  type="button"
                  onClick={handleExecuteImport}
                  disabled={importing}
                  className="px-3 py-1 rounded bg-[#51DCC8] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50"
                >
                  {importing ? "Importing..." : "2. Commit Import"}
                </button>
              </div>
            </div>
          )}

          {importResult && (
            <div className="p-3 rounded bg-[#0B1019] border border-emerald-900/50 text-xs font-mono text-emerald-300">
              Import Result: {importResult.status}. Remapped: {importResult.remapped_count}.
            </div>
          )}
        </div>
      </div>

      {/* Two Column Layout: Availability & Relinking vs Duplicate Media */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Availability & Relinking */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">Physical Media Availability &amp; Relinking</h2>
          <div className="flex gap-2">
            <input
              type="text"
              value={checkVersionId}
              onChange={(e) => setCheckVersionId(e.target.value)}
              placeholder="Enter Version or Video ID..."
              className="flex-1 px-3 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
            />
            <button
              type="button"
              onClick={handleCheckAvailability}
              disabled={checkingAvail}
              className="px-3 py-1.5 rounded bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-white border border-[#243149]"
            >
              Check Availability
            </button>
          </div>

          {availability && (
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149] space-y-2 text-xs font-mono">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Status:</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] uppercase ${
                    availability.availability === "available"
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                      : "bg-rose-950 text-rose-300 border border-rose-800"
                  }`}
                >
                  {availability.availability}
                </span>
              </div>
              <p className="text-slate-300 truncate">Path: {availability.file_path || "None"}</p>
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
                    className="w-full px-2 py-1 rounded bg-[#111827] border border-[#243149] text-xs text-white font-mono"
                  />
                  <button
                    type="submit"
                    disabled={relinking}
                    className="w-full py-1 rounded bg-[#9B8CFF] text-[#080B12] text-xs font-semibold font-mono"
                  >
                    {relinking ? "Relinking..." : "Relink File Asset"}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>

        {/* Duplicate Media Detector */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <h2 className="text-sm font-semibold text-[#F5F7FB]">
              Duplicate Media Groups ({duplicates.length})
            </h2>
            <span className="text-[10px] font-mono text-slate-400">SHA-256 Deduplication</span>
          </div>

          {duplicates.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 font-mono">
              Zero duplicate video files detected across roots.
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {duplicates.map((dup) => (
                <div
                  key={dup.sha256}
                  className="p-2.5 rounded bg-[#0B1019] border border-[#243149] space-y-1 text-xs font-mono"
                >
                  <div className="flex items-center justify-between text-[#9B8CFF]">
                    <span className="truncate max-w-[200px]">Hash: {dup.sha256.slice(0, 16)}â€¦</span>
                    <span className="text-slate-400">{dup.locations_count} locations</span>
                  </div>
                  <div className="text-[11px] text-slate-400 space-y-0.5">
                    {dup.locations.map((loc) => (
                      <div key={loc.location_id} className="truncate text-slate-300">
                        â€¢ {loc.rel_path} ({loc.availability})
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

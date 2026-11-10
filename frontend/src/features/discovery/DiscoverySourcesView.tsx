import { useEffect, useState } from "react";
import {
  createDiscoveryLibrary,
  fetchDiscoveryLibraries,
  fetchDiscoveryRoots,
  fetchScanRuns,
  registerDiscoveryRoot,
  scanDiscoveryRoot,
  type DiscoveryLibrary,
  type DiscoveryRoot,
  type ScanRun,
} from "../../services/api";

interface DiscoverySourcesViewProps {
  onNavigate?: (section: string) => void;
}

export function DiscoverySourcesView({ onNavigate }: DiscoverySourcesViewProps) {
  const [libraries, setLibraries] = useState<DiscoveryLibrary[]>([]);
  const [roots, setRoots] = useState<DiscoveryRoot[]>([]);
  const [selectedLibraryId, setSelectedLibraryId] = useState<string>("");
  const [selectedRootId, setSelectedRootId] = useState<string>("");
  const [scanRuns, setScanRuns] = useState<ScanRun[]>([]);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [lastScanSummary, setLastScanSummary] = useState<{
    discovered: number;
    newAssets: number;
    status: string;
  } | null>(null);

  // New Root Form
  const [newPath, setNewPath] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newPolicy, setNewPolicy] = useState("local_only");
  const [registering, setRegistering] = useState(false);

  // New Library Modal
  const [showLibModal, setShowLibModal] = useState(false);
  const [libLabel, setLibLabel] = useState("");
  const [libProfile, setLibProfile] = useState("fully_offline_no_ai");

  // Scanning & Loading States
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      setLoading(true);
      try {
        const rawLibs = await fetchDiscoveryLibraries();
        let libs = Array.isArray(rawLibs) ? rawLibs : [];
        if (libs.length === 0) {
          // Auto-initialize default local library if none exist
          const defaultLib = await createDiscoveryLibrary("Primary Studio MediaVault");
          libs = [defaultLib];
        }
        if (!cancelled) {
          setLibraries(libs);
          const activeLib = libs[0].id;
          setSelectedLibraryId(activeLib);
          const rts = await fetchDiscoveryRoots(activeLib);
          setRoots(Array.isArray(rts) ? rts : []);
          if (rts && rts.length > 0) {
            setSelectedRootId(rts[0].id);
            const runs = await fetchScanRuns(rts[0].id).catch(() => []);
            setScanRuns(Array.isArray(runs) ? runs : []);
          }
          setFeedback(null);
        }
      } catch (err) {
        if (!cancelled) {
          setFeedback(err instanceof Error ? err.message : "Failed to load libraries");
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

  async function handleSelectLibrary(libId: string) {
    setSelectedLibraryId(libId);
    setFeedback(null);
    try {
      const rts = await fetchDiscoveryRoots(libId);
      setRoots(rts);
      if (rts.length > 0) {
        setSelectedRootId(rts[0].id);
        const runs = await fetchScanRuns(rts[0].id).catch(() => []);
        setScanRuns(runs);
      } else {
        setSelectedRootId("");
        setScanRuns([]);
      }
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Failed to load roots for library");
    }
  }

  async function handleSelectRoot(rootId: string) {
    setSelectedRootId(rootId);
    try {
      const runs = await fetchScanRuns(rootId);
      setScanRuns(runs);
    } catch {
      // Handled
    }
  }

  async function handleRegisterRoot(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedLibraryId || !newPath.trim()) return;
    setRegistering(true);
    setFeedback(null);
    try {
      const newRoot = await registerDiscoveryRoot(
        selectedLibraryId,
        newPath.trim(),
        newPolicy,
        newLabel.trim() || undefined
      );
      setRoots((prev) => [newRoot, ...prev]);
      setSelectedRootId(newRoot.id);
      setNewPath("");
      setNewLabel("");
      setFeedback(`Root registered: ${newRoot.label || newRoot.id}`);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Failed to register discovery root");
    } finally {
      setRegistering(false);
    }
  }

  async function handleScanNow() {
    if (!selectedRootId) return;
    setScanning(true);
    setFeedback(null);
    try {
      const scan = await scanDiscoveryRoot(selectedRootId);
      const discovered = scan.counts.discovered_media ?? 0;
      const newAssets = scan.counts.new_assets ?? 0;
      setLastScanSummary({
        discovered,
        newAssets,
        status: scan.status,
      });
      setFeedback(
        `Scan finished with status: ${scan.status}. Discovered media: ${discovered}, new assets: ${newAssets}.`
      );
      const runs = await fetchScanRuns(selectedRootId);
      setScanRuns(runs);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }

  async function handleCreateLib(e: React.FormEvent) {
    e.preventDefault();
    if (!libLabel.trim()) return;
    try {
      const lib = await createDiscoveryLibrary(libLabel.trim(), libProfile);
      setLibraries((prev) => [...prev, lib]);
      setSelectedLibraryId(lib.id);
      setShowLibModal(false);
      setLibLabel("");
      setRoots([]);
      setScanRuns([]);
      setFeedback(`Library created: ${lib.label}`);
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Failed to create library");
    }
  }

  const selectedRoot = roots.find((r) => r.id === selectedRootId);

  return (
    <div className="space-y-6">
      {/* Cinematic Header & Library Selector */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30">
                MEDIA INGESTION &amp; DISCOVERY
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
                DENY-BY-DEFAULT SANDBOX
              </span>
            </div>
            <h1 className="text-lg font-semibold text-[#F5F7FB] mt-1 tracking-tight">
              1. Add &amp; Watch Folders
            </h1>
            <p className="text-xs text-[#A2AEC0] mt-0.5">
              Secure media boundaries. Only approved paths in <code className="text-[#9B8CFF] font-mono">ALLOWED_MEDIA_ROOTS</code> can be scanned and indexed.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <div className="flex flex-col text-right hidden sm:flex">
              <span className="text-[10px] font-mono text-slate-400">Active Library:</span>
              <span className="text-xs font-mono font-medium text-white truncate max-w-[200px]">
                {(Array.isArray(libraries) && libraries.find((l) => l.id === selectedLibraryId)?.label) || "Loading..."}
              </span>
            </div>
            <select
              aria-label="Select Media Library"
              value={selectedLibraryId}
              onChange={(e) => void handleSelectLibrary(e.target.value)}
              className="px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#F5F7FB] focus:border-[#9B8CFF] focus:outline-none"
            >
              {(Array.isArray(libraries) ? libraries : []).map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label} ({l.roots_count} roots)
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setShowLibModal(true)}
              className="px-3 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#9B8CFF] border border-[#243149] transition-colors"
            >
              + New Library
            </button>
          </div>
        </div>

        {/* Dynamic Status / Feedback Banner */}
        {feedback && (
          <div
            role="status"
            className={`p-3 rounded-control border text-xs font-mono flex items-center justify-between gap-2 ${
              feedback.toLowerCase().includes("fail") || feedback.toLowerCase().includes("error")
                ? "bg-rose-950/40 border-rose-800/80 text-[#FF7386]"
                : "bg-emerald-950/40 border-emerald-800/80 text-[#51DCC8]"
            }`}
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  feedback.toLowerCase().includes("fail") || feedback.toLowerCase().includes("error")
                    ? "bg-[#FF7386]"
                    : "bg-[#51DCC8]"
                }`}
              />
              <span>{feedback}</span>
            </div>
            {lastScanSummary && onNavigate && (
              <button
                type="button"
                onClick={() => onNavigate("media-library")}
                className="px-2.5 py-1 rounded bg-[#080B12] hover:bg-[#172235] border border-[#243149] text-xs font-mono text-[#9B8CFF] transition-colors shrink-0"
              >
                View in Media Library &rarr;
              </button>
            )}
          </div>
        )}
      </div>

      {/* Main Grid: Roots Master List & Register Form */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 8 Cols: Registered Media Roots & Scan Runs */}
        <div className="lg:col-span-8 p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <div>
              <h2 className="text-sm font-semibold text-[#F5F7FB]">
                Active Discovery Roots ({roots.length})
              </h2>
              <p className="text-[11px] font-mono text-[#A2AEC0] mt-0.5">
                Directories monitored for video imports and asset discovery
              </p>
            </div>
            {selectedRootId && (
              <button
                type="button"
                onClick={() => void handleScanNow()}
                disabled={scanning}
                className="px-3.5 py-1.5 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50 transition-colors shadow-sm flex items-center gap-1.5"
              >
                {scanning && <span className="h-2 w-2 rounded-full bg-[#080B12] animate-ping" />}
                {scanning ? "Scanning Root..." : "Scan Selected Root Now"}
              </button>
            )}
          </div>

          {loading ? (
            <div className="py-12 text-center text-xs text-slate-400 font-mono space-y-2">
              <div className="inline-block h-5 w-5 border-2 border-[#9B8CFF] border-t-transparent rounded-full animate-spin" />
              <p>Loading discovery roots from vault database...</p>
            </div>
          ) : roots.length === 0 ? (
            <div className="py-10 text-center rounded-control bg-[#0B1019] border border-[#243149]/60 p-6 space-y-3">
              <span className="text-sm font-semibold text-slate-200">No media roots registered for this library yet</span>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                Use the registration form to authorize your video directories (e.g. <code className="text-[#9B8CFF] font-mono">./sample_data</code> or your media drive).
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
              {roots.map((root) => {
                const isSelected = root.id === selectedRootId;
                return (
                  <div
                    key={root.id}
                    onClick={() => void handleSelectRoot(root.id)}
                    className={`p-3 rounded-control border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-[#172235] border-[#9B8CFF] text-[#F5F7FB] shadow-sm"
                        : "bg-[#0B1019] border-[#243149] text-slate-300 hover:bg-[#172235]/60 hover:border-[#334366]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={`h-2 w-2 rounded-full shrink-0 ${
                            isSelected ? "bg-[#9B8CFF]" : "bg-slate-600"
                          }`}
                        />
                        <span className="text-xs font-semibold text-[#F5F7FB] truncate">
                          {root.label || root.id}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase font-semibold ${
                            root.policy === "local_only"
                              ? "bg-emerald-950/60 text-[#51DCC8] border border-emerald-800"
                              : "bg-amber-950/60 text-[#F4BF69] border border-amber-800"
                          }`}
                        >
                          {root.policy}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#080B12] text-slate-400 border border-[#243149]">
                          {root.status}
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 text-[11px] font-mono text-[#A2AEC0] flex flex-wrap items-center gap-4">
                      <span className="text-slate-400">Type: <span className="text-slate-200">{root.root_type}</span></span>
                      <span className="text-slate-400">Tracked Locations: <span className="text-[#9B8CFF] font-semibold">{root.locations_count}</span></span>
                      <span className="text-slate-400">
                        Last Scan: <span className="text-slate-300">{root.last_scan_at ? new Date(root.last_scan_at).toLocaleString() : "Never"}</span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Scan Runs History */}
          <div className="pt-4 border-t border-[#243149] space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-[#F5F7FB]">
                Scan Execution History {selectedRoot && `for "${selectedRoot.label || selectedRoot.id.slice(0, 8)}"`}
              </h3>
              {scanRuns.length > 0 && onNavigate && (
                <button
                  type="button"
                  onClick={() => onNavigate("media-library")}
                  className="text-[11px] font-mono text-[#9B8CFF] hover:underline"
                >
                  Explore in Media Library &rarr;
                </button>
              )}
            </div>

            {scanRuns.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500 font-mono bg-[#0B1019] rounded-control border border-[#243149]/40">
                No scan runs recorded yet for this root. Click &quot;Scan Selected Root Now&quot; above to discover media files.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-control border border-[#243149]/60">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="bg-[#0B1019] border-b border-[#243149] text-slate-400">
                      <th className="py-2 px-3">Scan ID</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 px-3">Scanned Files</th>
                      <th className="py-2 px-3">Discovered Media</th>
                      <th className="py-2 px-3">New Assets</th>
                      <th className="py-2 px-3">Started</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#243149]/40 bg-[#080B12] text-slate-300">
                    {scanRuns.map((r) => (
                      <tr key={r.id} className="hover:bg-[#172235]/40 transition-colors">
                        <td className="py-2 px-3 text-[#9B8CFF]">{r.id.slice(0, 8)}&hellip;</td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-semibold ${
                              r.status === "completed"
                                ? "text-[#51DCC8] bg-emerald-950/40 border border-emerald-900"
                                : r.status === "running"
                                ? "text-[#F4BF69] bg-amber-950/40 border border-amber-900"
                                : "text-[#FF7386] bg-rose-950/40 border border-rose-900"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="py-2 px-3">{r.counts?.scanned_files ?? 0}</td>
                        <td className="py-2 px-3 text-[#51DCC8] font-semibold">{r.counts?.discovered_media ?? 0}</td>
                        <td className="py-2 px-3 text-[#9B8CFF] font-semibold">{r.counts?.new_assets ?? 0}</td>
                        <td className="py-2 px-3 text-[11px] text-slate-400">
                          {new Date(r.started_at).toLocaleTimeString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right 4 Cols: Register New Root Form */}
        <div className="lg:col-span-4 p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <div className="border-b border-[#243149] pb-3">
            <h2 className="text-sm font-semibold text-[#F5F7FB]">Register New Media Root</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Add a directory path to the selected library
            </p>
          </div>

          <form onSubmit={(e) => void handleRegisterRoot(e)} className="space-y-3.5 font-sans">
            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Directory Path:</label>
              <input
                type="text"
                required
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                placeholder="./sample_data or C:/Videos"
                className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:border-[#9B8CFF] focus:outline-none transition-colors"
              />
              <p className="text-[10px] text-slate-400 font-mono">
                Must be an allowed root (e.g. <code className="text-[#9B8CFF]">./sample_data</code>).
              </p>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Friendly Label (Optional):</label>
              <input
                type="text"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g. Studio B-Roll Drive"
                className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-white focus:border-[#9B8CFF] focus:outline-none transition-colors"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Enclave Privacy Policy:</label>
              <select
                value={newPolicy}
                onChange={(e) => setNewPolicy(e.target.value)}
                className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:border-[#9B8CFF] focus:outline-none"
              >
                <option value="local_only">local_only (Strict zero-cloud egress)</option>
                <option value="allow_remote">allow_remote (Eligible for BYO-AI with consent)</option>
                <option value="quarantined">quarantined (Probing paused)</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={registering || !newPath.trim() || !selectedLibraryId}
              className="w-full py-2.5 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold disabled:opacity-50 transition-colors shadow-sm font-mono mt-2"
            >
              {registering ? "Registering Root..." : "+ Add Discovery Root"}
            </button>
          </form>

          {/* Quick Guidance Box */}
          <div className="p-3 rounded-control bg-[#0B1019] border border-[#243149] text-xs space-y-1.5 text-slate-400">
            <span className="font-semibold text-slate-300 block">How Discovery Works:</span>
            <p className="text-[11px] leading-relaxed">
              1. Register a folder to authorize read-only scanning.<br />
              2. Click &quot;Scan Selected Root Now&quot; to probe files.<br />
              3. Videos with SHA-256 fingerprints are indexed to your Media Library.
            </p>
          </div>
        </div>
      </div>

      {/* New Library Modal */}
      {showLibModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
          <div className="w-full max-w-sm bg-[#111827] border border-[#243149] rounded-panel p-5 shadow-2xl space-y-4">
            <div className="border-b border-[#243149] pb-2">
              <h3 className="text-xs font-semibold text-[#F5F7FB]">Create New Media Library</h3>
              <p className="text-[10px] text-slate-400 mt-0.5">Define a distinct media partition and execution profile</p>
            </div>
            <form onSubmit={(e) => void handleCreateLib(e)} className="space-y-3 font-sans">
              <div className="space-y-1">
                <label className="text-xs text-slate-300 font-medium">Library Name:</label>
                <input
                  type="text"
                  required
                  value={libLabel}
                  onChange={(e) => setLibLabel(e.target.value)}
                  placeholder="e.g. Documentary Footage 2026"
                  className="w-full px-2.5 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs text-white focus:border-[#9B8CFF] focus:outline-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-300 font-medium">Execution Profile:</label>
                <select
                  value={libProfile}
                  onChange={(e) => setLibProfile(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:border-[#9B8CFF] focus:outline-none"
                >
                  <option value="fully_offline_no_ai">fully_offline_no_ai</option>
                  <option value="local_ai">local_ai</option>
                  <option value="byok_remote_ai">byok_remote_ai</option>
                  <option value="hybrid_ai">hybrid_ai</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-[#243149]">
                <button
                  type="button"
                  onClick={() => setShowLibModal(false)}
                  className="px-3 py-1.5 rounded bg-[#172235] hover:bg-[#232f48] text-xs text-slate-300 border border-[#243149]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 rounded bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono"
                >
                  Create Library
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

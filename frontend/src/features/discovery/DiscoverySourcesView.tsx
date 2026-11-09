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

export function DiscoverySourcesView() {
  const [libraries, setLibraries] = useState<DiscoveryLibrary[]>([]);
  const [roots, setRoots] = useState<DiscoveryRoot[]>([]);
  const [selectedLibraryId, setSelectedLibraryId] = useState<string>("");
  const [selectedRootId, setSelectedRootId] = useState<string>("");
  const [scanRuns, setScanRuns] = useState<ScanRun[]>([]);
  const [feedback, setFeedback] = useState<string | null>(null);

  // New Root Form
  const [newPath, setNewPath] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newPolicy, setNewPolicy] = useState("local_only");
  const [registering, setRegistering] = useState(false);

  // New Library Form
  const [showLibModal, setShowLibModal] = useState(false);
  const [libLabel, setLibLabel] = useState("");
  const [libProfile, setLibProfile] = useState("fully_offline_no_ai");

  // Scanning State
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function loadData() {
      try {
        let libs = await fetchDiscoveryLibraries();
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
          setRoots(rts);
          if (rts.length > 0) {
            setSelectedRootId(rts[0].id);
            const runs = await fetchScanRuns(rts[0].id).catch(() => []);
            setScanRuns(runs);
          }
        }
      } catch (err) {
        if (!cancelled) setFeedback(err instanceof Error ? err.message : "Failed to load libraries");
      }
    }
    void loadData();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSelectLibrary(libId: string) {
    setSelectedLibraryId(libId);
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
    } catch {
      // Handled
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
      setFeedback(
        `Scan finished with status: ${scan.status}. Discovered media: ${
          scan.counts.discovered_media ?? 0
        }, new assets: ${scan.counts.new_assets ?? 0}.`
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
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Failed to create library");
    }
  }

  return (
    <div className="space-y-6">
      {/* Header & Library Selector */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30">
                TASK-4B MEDIA DISCOVERY
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
                DENY-BY-DEFAULT ROOTS
              </span>
            </div>
            <h1 className="text-lg font-semibold text-[#F5F7FB] mt-1">
              Library Sources &amp; Media Discovery Roots
            </h1>
            <p className="text-xs text-[#A2AEC0] mt-0.5">
              Secure discovery boundaries. Only authorized paths in ALLOWED_MEDIA_ROOTS can be indexed.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <select
              value={selectedLibraryId}
              onChange={(e) => handleSelectLibrary(e.target.value)}
              className="px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#F5F7FB] focus:border-[#9B8CFF] focus:outline-none"
            >
              {libraries.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.label} ({l.execution_profile})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setShowLibModal(true)}
              className="px-3 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-[#9B8CFF] border border-[#243149]"
            >
              + New Library
            </button>
          </div>
        </div>

        {feedback && (
          <div className="p-2.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-[#51DCC8]">
            {feedback}
          </div>
        )}
      </div>

      {/* Main Grid: Roots Table & Register Form */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Roots Table */}
        <div className="lg:col-span-2 p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <div className="flex items-center justify-between border-b border-[#243149] pb-3">
            <h2 className="text-sm font-semibold text-[#F5F7FB]">
              Active Discovery Roots ({roots.length})
            </h2>
            {selectedRootId && (
              <button
                type="button"
                onClick={handleScanNow}
                disabled={scanning}
                className="px-3.5 py-1.5 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold font-mono disabled:opacity-50 transition-colors shadow-sm"
              >
                {scanning ? "Scanning Root..." : "Scan Selected Root Now"}
              </button>
            )}
          </div>

          {roots.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-400 font-mono">
              No media roots registered for this library. Use the form on the right to register one.
            </div>
          ) : (
            <div className="space-y-2">
              {roots.map((root) => {
                const isSelected = root.id === selectedRootId;
                return (
                  <div
                    key={root.id}
                    onClick={() => handleSelectRoot(root.id)}
                    className={`p-3 rounded-control border cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-[#172235] border-[#9B8CFF]/50 text-[#F5F7FB]"
                        : "bg-[#0B1019] border-[#243149] text-slate-300 hover:bg-[#172235]/60"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-[#F5F7FB]">
                        {root.label || root.id}
                      </span>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-[10px] font-mono px-2 py-0.5 rounded uppercase ${
                            root.policy === "local_only"
                              ? "bg-emerald-950/60 text-emerald-400 border border-emerald-800"
                              : "bg-amber-950/60 text-amber-400 border border-amber-800"
                          }`}
                        >
                          {root.policy}
                        </span>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#080B12] text-slate-400 border border-[#243149]">
                          {root.status}
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 text-[11px] font-mono text-slate-400 flex flex-wrap items-center gap-4">
                      <span>Type: {root.root_type}</span>
                      <span>Tracked Assets: {root.locations_count}</span>
                      <span>
                        Last Scan: {root.last_scan_at ? new Date(root.last_scan_at).toLocaleString() : "Never"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Scan Runs History */}
          <div className="pt-4 border-t border-[#243149] space-y-3">
            <h3 className="text-xs font-semibold text-[#F5F7FB]">
              Scan Execution History {selectedRootId && `for ${selectedRootId.slice(0, 8)}â€¦`}
            </h3>

            {scanRuns.length === 0 ? (
              <div className="py-4 text-center text-xs text-slate-500 font-mono">
                No scan runs recorded yet for this root.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-[#243149] text-slate-400">
                      <th className="py-1.5 px-2">Scan ID</th>
                      <th className="py-1.5 px-2">Status</th>
                      <th className="py-1.5 px-2">Scanned</th>
                      <th className="py-1.5 px-2">Discovered</th>
                      <th className="py-1.5 px-2">Started</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#243149]/40 text-slate-300">
                    {scanRuns.map((r) => (
                      <tr key={r.id} className="hover:bg-[#172235]/40">
                        <td className="py-1.5 px-2 text-[#9B8CFF]">{r.id.slice(0, 8)}â€¦</td>
                        <td className="py-1.5 px-2">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] uppercase ${
                              r.status === "completed"
                                ? "text-emerald-400 bg-emerald-950/40"
                                : r.status === "running"
                                ? "text-amber-400 bg-amber-950/40"
                                : "text-rose-400 bg-rose-950/40"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="py-1.5 px-2">{r.counts?.scanned_files ?? 0}</td>
                        <td className="py-1.5 px-2">{r.counts?.discovered_media ?? 0}</td>
                        <td className="py-1.5 px-2 text-[10px] text-slate-400">
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

        {/* Right Col: Register New Root */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">Register New Media Root</h2>
          <form onSubmit={handleRegisterRoot} className="space-y-3 font-sans">
            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Directory Path:</label>
              <input
                type="text"
                required
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                placeholder="C:/Videos or /data/media"
                className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-white focus:border-[#9B8CFF] focus:outline-none"
              />
              <p className="text-[10px] text-slate-500 font-mono">
                Must be an absolute or canonical path allowed by host configuration.
              </p>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Friendly Label:</label>
              <input
                type="text"
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                placeholder="e.g. Master Footing SSD"
                className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs text-white focus:outline-none"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs text-slate-300 font-medium">Enclave Policy:</label>
              <select
                value={newPolicy}
                onChange={(e) => setNewPolicy(e.target.value)}
                className="w-full px-3 py-1.5 rounded-control bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
              >
                <option value="local_only">local_only (Strict zero-cloud egress)</option>
                <option value="allow_remote">allow_remote (Eligible for BYO-AI with consent)</option>
                <option value="quarantined">quarantined (Probing paused)</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={registering || !newPath.trim()}
              className="w-full py-2 rounded-control bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] text-xs font-semibold disabled:opacity-50 transition-colors shadow-sm"
            >
              {registering ? "Registering Root..." : "+ Add Discovery Root"}
            </button>
          </form>
        </div>
      </div>

      {/* New Library Modal */}
      {showLibModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-sm bg-[#111827] border border-[#243149] rounded-panel p-5 shadow-2xl space-y-4">
            <h3 className="text-xs font-semibold text-[#F5F7FB]">Create New Media Library</h3>
            <form onSubmit={handleCreateLib} className="space-y-3 font-sans">
              <div className="space-y-1">
                <label className="text-xs text-slate-300 font-medium">Library Name:</label>
                <input
                  type="text"
                  required
                  value={libLabel}
                  onChange={(e) => setLibLabel(e.target.value)}
                  placeholder="e.g. Documentary Project 2026"
                  className="w-full px-2.5 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-300 font-medium">Execution Profile:</label>
                <select
                  value={libProfile}
                  onChange={(e) => setLibProfile(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded bg-[#0B1019] border border-[#243149] text-xs font-mono text-white"
                >
                  <option value="fully_offline_no_ai">fully_offline_no_ai</option>
                  <option value="local_ai">local_ai</option>
                  <option value="byok_remote_ai">byok_remote_ai</option>
                  <option value="hybrid_ai">hybrid_ai</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowLibModal(false)}
                  className="px-3 py-1 rounded bg-[#172235] text-xs text-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 rounded bg-[#9B8CFF] text-[#080B12] text-xs font-semibold"
                >
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

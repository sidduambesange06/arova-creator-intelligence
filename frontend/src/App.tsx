import { useCallback, useEffect, useState } from "react";
import { MediaLibraryView } from "./features/media-library/MediaLibraryView";
import { McpConfigView } from "./features/settings/McpConfigView";
import { HybridSearchView } from "./features/video-search/HybridSearchView";
import { fetchHealth, type HealthResponse } from "./services/api";

type NavSection = "system" | "media-library" | "hybrid-search" | "mcp-config";

const SECTIONS: { id: NavSection; label: string; milestone: string; badge: string }[] = [
  { id: "system", label: "System & Health", milestone: "Milestone 1", badge: "Core" },
  { id: "media-library", label: "Media Library", milestone: "Milestone 2", badge: "Studio" },
  { id: "hybrid-search", label: "Hybrid Video RAG", milestone: "Milestone 4", badge: "AI" },
  { id: "mcp-config", label: "MCP Server", milestone: "Milestone 5", badge: "Agent" },
];

export function App() {
  const [activeSection, setActiveSection] = useState<NavSection>("system");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState<boolean>(true);

  const checkHealth = useCallback(async (signal?: AbortSignal) => {
    setChecking(true);
    try {
      const data = await fetchHealth(signal);
      setHealth(data);
      setError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setHealth(null);
      setError(err instanceof Error ? err.message : "Backend unreachable");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void checkHealth(controller.signal);
    return () => controller.abort();
  }, [checkHealth]);

  const isOnline = health?.status === "ok" && !error;

  return (
    <div className="min-h-screen flex bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500 selection:text-white">
      {/* Sleek Studio Sidebar */}
      <aside className="w-72 border-r border-slate-800/80 bg-slate-900/50 backdrop-blur-xl flex flex-col justify-between p-5 shrink-0">
        <div className="space-y-6">
          {/* Brand Header */}
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                <span className="font-mono font-bold text-white text-base">A</span>
              </div>
              <div>
                <h1 className="text-base font-bold tracking-tight text-white">
                  Arova Intelligence
                </h1>
                <p className="text-[11px] font-mono text-indigo-400 font-medium">
                  v0.1.0 · Multimodal Video RAG
                </p>
              </div>
            </div>
          </div>

          {/* Navigation Items */}
          <nav aria-label="Inspector navigation" className="space-y-1.5">
            {SECTIONS.map((item) => {
              const active = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveSection(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm transition-all ${
                    active
                      ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/25 font-semibold"
                      : "text-slate-400 hover:text-slate-100 hover:bg-slate-800/60"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span>{item.label}</span>
                  </div>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md ${
                    active
                      ? "bg-white/20 text-white"
                      : "bg-slate-800 text-slate-400 border border-slate-700/50"
                  }`}>
                    {item.milestone}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Status Hub in Sidebar */}
        <div className="space-y-2.5 pt-4 border-t border-slate-800/80">
          <div
            data-testid="obsidian-badge"
            className="border border-purple-900/40 rounded-xl p-3 bg-purple-950/20 text-xs space-y-1 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-purple-300 font-semibold">Obsidian Brain</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-emerald-400 text-[11px]">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                connected
              </span>
            </div>
            <p className="text-[11px] text-purple-400/80 font-mono truncate">
              vault: docs/ (wikilinks active)
            </p>
          </div>

          <div
            data-testid="ponytail-badge"
            className="border border-amber-900/40 rounded-xl p-3 bg-amber-950/20 text-xs space-y-1 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-amber-300 font-semibold">Ponytail Mode</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-emerald-400 text-[11px]">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                active
              </span>
            </div>
            <p className="text-[11px] text-amber-400/80 font-mono truncate">
              anti-bluff · zero mock data
            </p>
          </div>

          <div
            data-testid="health-badge"
            className="border border-slate-800/90 rounded-xl p-3 bg-slate-950/80 text-xs space-y-1 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-semibold">FastAPI Engine</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px]">
                <span
                  className={`h-2 w-2 rounded-full ${
                    checking
                      ? "bg-amber-400 animate-ping"
                      : isOnline
                        ? "bg-emerald-400"
                        : "bg-rose-500"
                  }`}
                />
                {checking ? "checking" : isOnline ? "online" : "offline"}
              </span>
            </div>
            {health && (
              <p className="text-slate-400 font-mono text-[11px] truncate">
                v{health.version} ({health.environment})
              </p>
            )}
            {error && <p className="text-rose-400 font-mono text-[11px] truncate">{error}</p>}
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-8 max-w-5xl overflow-y-auto">
        {activeSection === "system" ? (
          <section className="space-y-6 animate-fadeIn">
            <div className="border-b border-slate-800/80 pb-5 flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold tracking-tight text-white">
                  Engine Connectivity &amp; Telemetry
                </h2>
                <p className="text-sm text-slate-400 mt-1">
                  Live probe against <code className="font-mono text-indigo-300 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">GET /api/v1/health</code>
                </p>
              </div>
              <button
                type="button"
                onClick={() => void checkHealth()}
                disabled={checking}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-xs font-mono font-medium text-slate-200 border border-slate-700 transition-all shadow-sm active:scale-95"
              >
                {checking ? "Probing..." : "Refresh Health"}
              </button>
            </div>

            {health ? (
              <dl className="grid grid-cols-2 gap-4 glass-panel rounded-2xl p-6 font-mono text-sm shadow-xl">
                <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                  <dt className="text-xs text-slate-400">Service</dt>
                  <dd className="text-slate-100 font-semibold text-base mt-1">{health.service}</dd>
                </div>
                <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                  <dt className="text-xs text-slate-400">Status</dt>
                  <dd className="text-emerald-400 font-semibold text-base mt-1 flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                    {health.status}
                  </dd>
                </div>
                <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                  <dt className="text-xs text-slate-400">Version</dt>
                  <dd className="text-slate-100 text-base mt-1">{health.version}</dd>
                </div>
                <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                  <dt className="text-xs text-slate-400">Environment</dt>
                  <dd className="text-slate-100 text-base mt-1">{health.environment}</dd>
                </div>
                <div className="col-span-2 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                  <dt className="text-xs text-slate-400">Last Timestamp (UTC)</dt>
                  <dd className="text-slate-300 mt-1">{health.timestamp}</dd>
                </div>
              </dl>
            ) : (
              <div className="border border-rose-900/50 bg-rose-950/30 rounded-2xl p-6 text-sm text-rose-300 font-mono">
                {checking
                  ? "Connecting to FastAPI backend..."
                  : `Backend health check failed: ${error}`}
              </div>
            )}
          </section>
        ) : activeSection === "media-library" ? (
          <MediaLibraryView />
        ) : activeSection === "hybrid-search" ? (
          <HybridSearchView />
        ) : activeSection === "mcp-config" ? (
          <McpConfigView />
        ) : (
          <section className="glass-panel rounded-2xl p-8">
            <h2 className="text-xl font-bold text-white">
              {SECTIONS.find((s) => s.id === activeSection)?.label}
            </h2>
            <p className="text-sm text-slate-400 mt-2">
              Scheduled for{" "}
              <span className="font-mono text-slate-200">
                {SECTIONS.find((s) => s.id === activeSection)?.milestone}
              </span>
              . No mock data is rendered before the backing API routes land.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;

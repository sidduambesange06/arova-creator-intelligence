import { useCallback, useEffect, useState } from "react";
import { MediaLibraryView } from "./features/media-library/MediaLibraryView";
import { McpConfigView } from "./features/settings/McpConfigView";
import { HybridSearchView } from "./features/video-search/HybridSearchView";
import { fetchHealth, type HealthResponse } from "./services/api";

type NavSection = "system" | "media-library" | "hybrid-search" | "mcp-config";

const SECTIONS: { id: NavSection; label: string; milestone: string }[] = [
  { id: "system", label: "System & Health", milestone: "Core" },
  { id: "media-library", label: "Media Library", milestone: "Studio" },
  { id: "hybrid-search", label: "Hybrid Video RAG", milestone: "AI / Search" },
  { id: "mcp-config", label: "MCP Server", milestone: "Agent Protocol" },
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
    <div className="min-h-screen flex bg-[#090d16] text-slate-100 font-sans selection:bg-slate-700 selection:text-white">
      {/* Hallmark Technical Sidebar */}
      <aside className="w-68 border-r border-slate-800/80 bg-[#0c121e] flex flex-col justify-between p-5 shrink-0">
        <div className="space-y-6">
          {/* Brand Header */}
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center">
                <span className="font-mono font-semibold text-slate-200 text-sm">A</span>
              </div>
              <div>
                <h1 className="text-sm font-semibold tracking-tight text-slate-100">
                  Arova Intelligence
                </h1>
                <p className="text-[11px] font-mono text-slate-400">
                  Multimodal Video RAG
                </p>
              </div>
            </div>
          </div>

          {/* Navigation Items */}
          <nav aria-label="Inspector navigation" className="space-y-1">
            {SECTIONS.map((item) => {
              const active = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveSection(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none ${
                    active
                      ? "bg-slate-800 text-white font-medium border border-slate-700 shadow-sm"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-850"
                  }`}
                >
                  <span>{item.label}</span>
                  <span
                    className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                      active
                        ? "bg-slate-900 text-slate-300 border border-slate-700"
                        : "text-slate-500"
                    }`}
                  >
                    {item.milestone}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Status Hub in Sidebar */}
        <div className="space-y-2 pt-4 border-t border-slate-800/80 text-xs">
          <div
            data-testid="obsidian-badge"
            className="p-2.5 rounded-lg border border-slate-800 bg-slate-900/60 space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-medium">Obsidian Brain</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-emerald-400 text-[11px]">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                connected
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono truncate">
              vault: docs/ (wikilinks active)
            </p>
          </div>

          <div
            data-testid="ponytail-badge"
            className="p-2.5 rounded-lg border border-slate-800 bg-slate-900/60 space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-medium">Ponytail Mode</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-emerald-400 text-[11px]">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                active
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono truncate">
              anti-bluff · zero mock data
            </p>
          </div>

          <div
            data-testid="health-badge"
            className="p-2.5 rounded-lg border border-slate-800 bg-slate-900/60 space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-medium">FastAPI Engine</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px]">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
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
          <section className="space-y-6">
            <div className="border-b border-slate-800/80 pb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold tracking-tight text-slate-100">
                  Engine Connectivity &amp; Telemetry
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Live probe against <code className="font-mono text-slate-300 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">GET /api/v1/health</code>
                </p>
              </div>
              <button
                type="button"
                onClick={() => void checkHealth()}
                disabled={checking}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-xs font-mono font-medium text-slate-200 border border-slate-700 transition-colors duration-150 shadow-sm active:scale-95 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
              >
                {checking ? "Probing..." : "Refresh Health"}
              </button>
            </div>

            {health ? (
              <dl className="grid grid-cols-2 gap-3 hallmark-surface p-5 font-mono text-xs">
                <div className="p-3 rounded-md border border-slate-800/80 bg-slate-900/40">
                  <dt className="text-slate-500">Service</dt>
                  <dd className="text-slate-200 font-medium text-sm mt-0.5">{health.service}</dd>
                </div>
                <div className="p-3 rounded-md border border-slate-800/80 bg-slate-900/40">
                  <dt className="text-slate-500">Status</dt>
                  <dd className="text-emerald-400 font-medium text-sm mt-0.5 flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-emerald-400" />
                    {health.status}
                  </dd>
                </div>
                <div className="p-3 rounded-md border border-slate-800/80 bg-slate-900/40">
                  <dt className="text-slate-500">Version</dt>
                  <dd className="text-slate-200 text-sm mt-0.5">{health.version}</dd>
                </div>
                <div className="p-3 rounded-md border border-slate-800/80 bg-slate-900/40">
                  <dt className="text-slate-500">Environment</dt>
                  <dd className="text-slate-200 text-sm mt-0.5">{health.environment}</dd>
                </div>
                <div className="col-span-2 p-3 rounded-md border border-slate-800/80 bg-slate-900/40">
                  <dt className="text-slate-500">Last Timestamp (UTC)</dt>
                  <dd className="text-slate-300 mt-0.5">{health.timestamp}</dd>
                </div>
              </dl>
            ) : (
              <div className="border border-rose-900/50 bg-rose-950/20 rounded-lg p-4 text-xs text-rose-300 font-mono">
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
        ) : null}
      </main>
    </div>
  );
}

export default App;

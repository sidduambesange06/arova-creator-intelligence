import { useCallback, useEffect, useState } from "react";
import { MediaLibraryView } from "./features/media-library/MediaLibraryView";
import { McpConfigView } from "./features/settings/McpConfigView";
import { HybridSearchView } from "./features/video-search/HybridSearchView";
import { fetchHealth, type HealthResponse } from "./services/api";

type NavSection = "media-library" | "hybrid-search" | "mcp-config" | "system";

const SECTIONS: { id: NavSection; label: string; tag: string }[] = [
  { id: "media-library", label: "Studio Media Library", tag: "Workstation" },
  { id: "hybrid-search", label: "Hybrid Video RAG & Q&A", tag: "AI / Search" },
  { id: "mcp-config", label: "MCP Agent Server", tag: "Protocol" },
  { id: "system", label: "Engine Telemetry & Health", tag: "Core" },
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
    <div className="min-h-screen flex bg-[#060911] text-slate-100 font-sans selection:bg-slate-700 selection:text-white">
      {/* Sidebar */}
      <aside className="w-64 border-r border-[#172338] bg-[#090e18] flex flex-col justify-between p-4 shrink-0 h-screen sticky top-0">
        <div className="space-y-6">
          {/* Brand Header */}
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <div className="h-8 w-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shadow-sm">
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
                    {item.tag}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Status Hub in Sidebar */}
        <div className="space-y-2 pt-4 border-t border-[#172338] text-xs">
          <div
            data-testid="health-badge"
            className="p-2.5 rounded-lg border border-[#172338] bg-[#0d1424] space-y-0.5"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-medium">FastAPI Engine</span>
              <span className="inline-flex items-center gap-1 font-mono text-[11px]">
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

      {/* Main Full-Screen Workstation Canvas */}
      <main className="flex-1 min-w-0 h-screen overflow-y-auto flex flex-col">
        {/* Studio Top Bar */}
        <header className="h-14 border-b border-[#172338] bg-[#090e18]/80 backdrop-blur px-6 flex items-center justify-between shrink-0 sticky top-0 z-20">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-200">
              {SECTIONS.find((s) => s.id === activeSection)?.label}
            </span>
            <span className="text-slate-600">/</span>
            <span className="text-[11px] font-mono text-slate-400">
              Local-First Multimodal Engine
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#0d1424] border border-[#172338] text-slate-300">
              Local-First · Cloud AI requires explicit opt-in
            </span>
            <button
              type="button"
              onClick={() => void checkHealth()}
              disabled={checking}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] font-mono text-slate-200 border border-slate-700 transition-colors duration-150 disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:outline-none"
            >
              {checking ? "Checking..." : "Sync Health"}
            </button>
          </div>
        </header>

        {/* Content Area Filling Screen */}
        <div className="flex-1 p-6 lg:p-8 w-full max-w-[1920px] mx-auto">
          {activeSection === "system" ? (
            <section className="space-y-6">
              <div className="border-b border-[#172338] pb-4 flex items-center justify-between">
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
                <dl className="grid grid-cols-2 lg:grid-cols-4 gap-3 arova-surface p-5 font-mono text-xs">
                  <div className="p-3 rounded-md border border-[#172338] bg-[#090e18]">
                    <dt className="text-slate-500">Service</dt>
                    <dd className="text-slate-200 font-medium text-sm mt-0.5">{health.service}</dd>
                  </div>
                  <div className="p-3 rounded-md border border-[#172338] bg-[#090e18]">
                    <dt className="text-slate-500">Status</dt>
                    <dd className="text-emerald-400 font-medium text-sm mt-0.5 flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-400" />
                      {health.status}
                    </dd>
                  </div>
                  <div className="p-3 rounded-md border border-[#172338] bg-[#090e18]">
                    <dt className="text-slate-500">Version</dt>
                    <dd className="text-slate-200 text-sm mt-0.5">{health.version}</dd>
                  </div>
                  <div className="p-3 rounded-md border border-[#172338] bg-[#090e18]">
                    <dt className="text-slate-500">Environment</dt>
                    <dd className="text-slate-200 text-sm mt-0.5">{health.environment}</dd>
                  </div>
                  <div className="col-span-2 lg:col-span-4 p-3 rounded-md border border-[#172338] bg-[#090e18]">
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
        </div>
      </main>
    </div>
  );
}

export default App;

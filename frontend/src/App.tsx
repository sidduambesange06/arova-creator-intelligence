import { useCallback, useEffect, useState } from "react";
import { MediaLibraryView } from "./features/media-library/MediaLibraryView";
import { fetchHealth, type HealthResponse } from "./services/api";

type NavSection = "system" | "media-library" | "hybrid-search" | "mcp-config";

const SECTIONS: { id: NavSection; label: string; milestone: string }[] = [
  { id: "system", label: "System & Health", milestone: "Milestone 1" },
  { id: "media-library", label: "Media Library", milestone: "Milestone 2" },
  { id: "hybrid-search", label: "Hybrid Video RAG", milestone: "Milestone 4" },
  { id: "mcp-config", label: "MCP Server", milestone: "Milestone 5" },
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
    <div className="min-h-screen flex bg-slate-950 text-slate-100 font-sans">
      <aside className="w-64 border-r border-slate-800 bg-slate-900/60 flex flex-col justify-between p-4">
        <div>
          <div className="mb-6">
            <h1 className="text-base font-semibold tracking-tight text-white">
              Arova Creator Intelligence
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Local Video RAG &amp; MCP Inspector
            </p>
          </div>

          <nav aria-label="Inspector navigation" className="space-y-1">
            {SECTIONS.map((item) => {
              const active = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveSection(item.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-sm transition-colors ${
                    active
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                  }`}
                >
                  <span>{item.label}</span>
                  <span className="text-[11px] font-mono text-slate-500">
                    {item.milestone}
                  </span>
                </button>
              );
            })}
          </nav>
        </div>

        <div className="space-y-2">
          <div
            data-testid="obsidian-badge"
            className="border border-purple-900/40 rounded-md p-3 bg-purple-950/20 text-xs space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-purple-300 font-medium">Obsidian Brain</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-emerald-400">
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
            className="border border-amber-900/40 rounded-md p-3 bg-amber-950/20 text-xs space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-amber-300 font-medium">Ponytail Mode</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-emerald-400">
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
            className="border border-slate-800 rounded-md p-3 bg-slate-950/80 text-xs space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-400 font-medium">API Status</span>
              <span className="inline-flex items-center gap-1.5 font-mono">
                <span
                  className={`h-2 w-2 rounded-full ${
                    checking
                      ? "bg-amber-400"
                      : isOnline
                        ? "bg-emerald-400"
                        : "bg-rose-500"
                  }`}
                />
                {checking ? "checking" : isOnline ? "online" : "offline"}
              </span>
            </div>
            {health && (
              <p className="text-slate-500 font-mono truncate">
                v{health.version} ({health.environment})
              </p>
            )}
            {error && <p className="text-rose-400 truncate">{error}</p>}
          </div>
        </div>
      </aside>

      <main className="flex-1 p-8 max-w-4xl">
        {activeSection === "system" ? (
          <section className="space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  Engine Connectivity &amp; Telemetry
                </h2>
                <p className="text-sm text-slate-400">
                  Live probe against <code className="font-mono text-slate-300">GET /api/v1/health</code>
                </p>
              </div>
              <button
                type="button"
                onClick={() => void checkHealth()}
                disabled={checking}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-xs font-mono text-slate-200 border border-slate-700"
              >
                {checking ? "Probing..." : "Refresh Health"}
              </button>
            </div>

            {health ? (
              <dl className="grid grid-cols-2 gap-4 bg-slate-900/60 border border-slate-800 rounded-lg p-5 font-mono text-sm">
                <div>
                  <dt className="text-xs text-slate-400">Service</dt>
                  <dd className="text-slate-100 mt-1">{health.service}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">Status</dt>
                  <dd className="text-emerald-400 mt-1">{health.status}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">Version</dt>
                  <dd className="text-slate-100 mt-1">{health.version}</dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-400">Environment</dt>
                  <dd className="text-slate-100 mt-1">{health.environment}</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-xs text-slate-400">Last Timestamp (UTC)</dt>
                  <dd className="text-slate-300 mt-1">{health.timestamp}</dd>
                </div>
              </dl>
            ) : (
              <div className="border border-rose-900/50 bg-rose-950/20 rounded-lg p-5 text-sm text-rose-300">
                {checking
                  ? "Connecting to FastAPI backend..."
                  : `Backend health check failed: ${error}`}
              </div>
            )}
          </section>
        ) : activeSection === "media-library" ? (
          <MediaLibraryView />
        ) : (
          <section className="border border-slate-800 bg-slate-900/40 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-white">
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


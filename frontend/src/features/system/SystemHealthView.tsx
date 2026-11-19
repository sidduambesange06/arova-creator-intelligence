import { useEffect, useState } from "react";
import {
  fetchHealth,
  fetchSystemTelemetry,
  type HealthResponse,
  type SystemTelemetry,
} from "../../services/api";

const SHORTCUTS = [
  { key: "Ctrl + K / Cmd + K", desc: "Open global command palette" },
  { key: "Space", desc: "Toggle Play / Pause in Video Workstation" },
  { key: "J / K / L", desc: "Shuttle backward / Pause / Shuttle forward" },
  { key: "I / O", desc: "Set In / Out markers for lossless clip export" },
  { key: "/", desc: "Focus search query input" },
  { key: "Esc", desc: "Dismiss active modal, palette, or drawer" },
];

const SBOM_COMPONENTS = [
  { name: "FastAPI", role: "Backend REST API Engine", license: "MIT" },
  { name: "SQLite + FTS5", role: "Relational Memory & Lexical Search", license: "Public Domain" },
  { name: "Faster-Whisper", role: "Local ASR Speech Recognition", license: "MIT" },
  { name: "Sentence-Transformers", role: "Bi-Encoder & Cross-Encoder RAG", license: "Apache 2.0" },
  { name: "FastMCP", role: "Model Context Protocol Tool Server", license: "MIT" },
  { name: "React 18", role: "Workstation User Interface", license: "MIT" },
  { name: "TailwindCSS", role: "Cinematic Instrument Design Engine", license: "MIT" },
  { name: "Vite", role: "Frontend Compiler & Bundler", license: "MIT" },
];

interface SystemHealthViewProps {
  health?: HealthResponse | null;
  checking?: boolean;
  error?: string | null;
  onRefresh?: () => void;
}

export function SystemHealthView({
  health: propHealth,
  checking: propChecking,
  error: propError,
  onRefresh,
}: SystemHealthViewProps = {}) {
  const [internalHealth, setInternalHealth] = useState<HealthResponse | null>(null);
  const [telemetry, setTelemetry] = useState<SystemTelemetry | null>(null);
  const [telemetryError, setTelemetryError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [internalError, setInternalError] = useState<string | null>(null);

  const health = propHealth !== undefined ? propHealth : internalHealth;
  const error = propError !== undefined ? propError : internalError;
  const checking = propChecking !== undefined ? propChecking : loading;

  // Appearance Preferences (persisted & applied to root HTML dataset)
  const [density, setDensity] = useState<"comfortable" | "compact">(() =>
    localStorage.getItem("arova_ui_density") === "compact" ? "compact" : "comfortable"
  );
  const [reducedMotion, setReducedMotion] = useState<boolean>(
    () => localStorage.getItem("arova_ui_reduced_motion") === "true"
  );

  useEffect(() => {
    document.documentElement.dataset.density = density;
    try {
      localStorage.setItem("arova_ui_density", density);
    } catch {
      // Ignore storage restrictions
    }
  }, [density]);

  useEffect(() => {
    document.documentElement.dataset.reducedMotion = reducedMotion ? "true" : "false";
    try {
      localStorage.setItem("arova_ui_reduced_motion", reducedMotion ? "true" : "false");
    } catch {
      // Ignore storage restrictions
    }
  }, [reducedMotion]);

  useEffect(() => {
    let cancelled = false;
    async function probe() {
      if (propHealth === undefined && propError === undefined) {
        setLoading(true);
        setInternalError(null);
        try {
          const h = await fetchHealth();
          if (!cancelled) setInternalHealth(h);
        } catch (err) {
          if (!cancelled) setInternalError(err instanceof Error ? err.message : "Backend unreachable");
        } finally {
          if (!cancelled) setLoading(false);
        }
      }
      try {
        const tel = await fetchSystemTelemetry();
        if (!cancelled) {
          setTelemetry(tel);
          setTelemetryError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setTelemetryError(err instanceof Error ? err.message : "Telemetry unavailable");
        }
      }
    }
    void probe();
    return () => {
      cancelled = true;
    };
  }, [propHealth, propError]);

  return (
    <div className="space-y-6">
      {/* Engine Status Header */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#51DCC8]/10 text-[#51DCC8] border border-[#51DCC8]/30">
                CORE SYSTEM TELEMETRY
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#172235] text-slate-400 border border-[#243149]">
                LOOPBACK 127.0.0.1
              </span>
            </div>
            <h1 className="text-lg font-semibold text-[#F5F7FB] mt-1">
              Engine Connectivity &amp; System Health
            </h1>
            <p className="text-xs text-[#A2AEC0]">
              Real-time health verification, background worker telemetry, and application preferences.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              if (onRefresh) onRefresh();
              void fetchSystemTelemetry()
                .then((tel) => {
                  setTelemetry(tel);
                  setTelemetryError(null);
                })
                .catch((err) => {
                  setTelemetryError(err instanceof Error ? err.message : "Telemetry unavailable");
                });
            }}
            disabled={checking}
            className="px-3.5 py-1.5 rounded-control bg-[#172235] hover:bg-[#232f48] text-xs font-mono text-slate-200 border border-[#243149] transition-colors disabled:opacity-50"
          >
            {checking ? "Probing..." : "Refresh Telemetry"}
          </button>
        </div>

        {health ? (
          <dl className="grid grid-cols-2 lg:grid-cols-4 gap-3 font-mono text-xs">
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Service</dt>
              <dd className="text-slate-200 font-medium text-sm mt-0.5">{health.service}</dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Status</dt>
              <dd className="text-[#51DCC8] font-medium text-sm mt-0.5 flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#51DCC8]" />
                {health.status}
              </dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Version</dt>
              <dd className="text-slate-200 text-sm mt-0.5">{health.version}</dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Environment</dt>
              <dd className="text-slate-200 text-sm mt-0.5">{health.environment}</dd>
            </div>
          </dl>
        ) : (
          <div className="p-3 rounded bg-rose-950/40 border border-rose-900 text-rose-300 text-xs font-mono">
            {loading ? "Probing FastAPI backend..." : `Health check failed: ${error}`}
          </div>
        )}
      </div>

      {/* Worker Telemetry Metrics */}
      {telemetryError && !telemetry && (
        <div role="alert" className="p-3 rounded-panel bg-amber-950/30 border border-amber-900/60 text-amber-300 text-xs font-mono">
          Worker telemetry unavailable: {telemetryError}
        </div>
      )}
      {telemetry && (
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">Worker Execution Telemetry</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 font-mono text-xs">
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Jobs Completed</dt>
              <dd className="text-lg font-bold text-emerald-400 mt-0.5">
                {telemetry.worker?.jobs_completed ?? 0}
              </dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Jobs Failed</dt>
              <dd className="text-lg font-bold text-rose-400 mt-0.5">
                {telemetry.worker?.jobs_failed ?? 0}
              </dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Last RTF</dt>
              <dd className="text-lg font-bold text-[#9B8CFF] mt-0.5">
                {telemetry.worker?.last_rtf ? `${telemetry.worker.last_rtf.toFixed(2)}x` : "--"}
              </dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Average RTF</dt>
              <dd className="text-lg font-bold text-[#51DCC8] mt-0.5">
                {telemetry.worker?.avg_rtf ? `${telemetry.worker.avg_rtf.toFixed(2)}x` : "--"}
              </dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Audio Processed</dt>
              <dd className="text-lg font-bold text-white mt-0.5">
                {telemetry.worker?.total_audio_sec ? `${telemetry.worker.total_audio_sec.toFixed(0)}s` : "0s"}
              </dd>
            </div>
            <div className="p-3 rounded bg-[#0B1019] border border-[#243149]">
              <dt className="text-slate-500">Processing Time</dt>
              <dd className="text-lg font-bold text-slate-300 mt-0.5">
                {telemetry.worker?.total_proc_sec ? `${telemetry.worker.total_proc_sec.toFixed(0)}s` : "0s"}
              </dd>
            </div>
          </div>
        </div>
      )}

      {/* Two Columns: Keyboard Shortcuts & Appearance Preferences */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Keyboard Shortcuts */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-3">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">Keyboard Navigation Cheatsheet</h2>
          <div className="space-y-1.5 font-mono text-xs">
            {SHORTCUTS.map((s) => (
              <div
                key={s.key}
                className="p-2 rounded bg-[#0B1019] border border-[#243149] flex items-center justify-between"
              >
                <span className="text-slate-300 font-sans">{s.desc}</span>
                <span className="px-2 py-0.5 rounded bg-[#172235] text-[#9B8CFF] border border-[#243149]">
                  {s.key}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Appearance & Accessibility */}
        <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
          <h2 className="text-sm font-semibold text-[#F5F7FB]">Appearance &amp; Accessibility</h2>

          <div className="space-y-3 font-sans text-xs">
            <div className="flex items-center justify-between p-3 rounded bg-[#0B1019] border border-[#243149]">
              <div>
                <p className="font-medium text-[#F5F7FB]">Interface Density</p>
                <p className="text-[11px] text-slate-400">Controls data padding in grids and tables.</p>
              </div>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => setDensity("comfortable")}
                  className={`px-2.5 py-1 rounded text-xs font-mono ${
                    density === "comfortable"
                      ? "bg-[#9B8CFF] text-[#080B12] font-semibold"
                      : "bg-[#172235] text-slate-400"
                  }`}
                >
                  Comfortable
                </button>
                <button
                  type="button"
                  onClick={() => setDensity("compact")}
                  className={`px-2.5 py-1 rounded text-xs font-mono ${
                    density === "compact"
                      ? "bg-[#9B8CFF] text-[#080B12] font-semibold"
                      : "bg-[#172235] text-slate-400"
                  }`}
                >
                  Compact
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between p-3 rounded bg-[#0B1019] border border-[#243149]">
              <div>
                <p className="font-medium text-[#F5F7FB]">Reduced Motion</p>
                <p className="text-[11px] text-slate-400">Disables animations for high-frequency video decoding.</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={reducedMotion}
                  onChange={(e) => setReducedMotion(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-[#172235] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#9B8CFF]" />
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* About & SBOM */}
      <div className="p-5 rounded-panel bg-[#111827] border border-[#243149] space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-[#243149] pb-3">
          <div>
            <h2 className="text-sm font-semibold text-[#F5F7FB]">
              About Arova Creator Intelligence
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Open-source, local-first multimodal video intelligence engine licensed under Apache 2.0.
            </p>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
            APACHE 2.0 LICENSED
          </span>
        </div>

        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-slate-300">Software Bill of Materials (SBOM)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-[#243149] text-slate-400">
                  <th className="py-1 px-2">Component</th>
                  <th className="py-1 px-2">Function</th>
                  <th className="py-1 px-2">License</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#243149]/40 text-slate-300">
                {SBOM_COMPONENTS.map((c) => (
                  <tr key={c.name} className="hover:bg-[#172235]/40">
                    <td className="py-1.5 px-2 text-[#9B8CFF] font-medium">{c.name}</td>
                    <td className="py-1.5 px-2">{c.role}</td>
                    <td className="py-1.5 px-2 text-[10px] text-slate-400">{c.license}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

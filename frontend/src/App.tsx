import { useCallback, useEffect, useState } from "react";
import { CommandPaletteModal, type CommandItem } from "./components/CommandPaletteModal";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { DatabaseExplorerView } from "./features/database-explorer/DatabaseExplorerView";
import { DiscoverySourcesView } from "./features/discovery/DiscoverySourcesView";
import { MediaLibraryView } from "./features/media-library/MediaLibraryView";
import { OverviewView } from "./features/overview/OverviewView";
import { PrivacyAiView } from "./features/privacy-ai/PrivacyAiView";
import { ProcessingJobsView } from "./features/processing/ProcessingJobsView";
import { McpConfigView } from "./features/settings/McpConfigView";
import { StorageBackupView } from "./features/storage/StorageBackupView";
import { SystemHealthView } from "./features/system/SystemHealthView";
import { HybridSearchView } from "./features/video-search/HybridSearchView";
import { VideoWorkstationView } from "./features/workstation/VideoWorkstationView";
import { fetchHealth, type HealthResponse } from "./services/api";

export type NavSection =
  | "overview"
  | "media-library"
  | "workstation"
  | "discovery-roots"
  | "processing-jobs"
  | "storage-backup"
  | "hybrid-search"
  | "privacy-ai"
  | "mcp-config"
  | "database-explorer"
  | "system";

interface NavGroup {
  name: string;
  items: {
    id: NavSection;
    label: string;
    tag: string;
  }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    name: "Workspace",
    items: [
      { id: "overview", label: "Mission Overview", tag: "Cockpit" },
      { id: "media-library", label: "Studio Media Library", tag: "Assets" },
      { id: "workstation", label: "Precision Workstation", tag: "Editor" },
    ],
  },
  {
    name: "Media Operations",
    items: [
      { id: "discovery-roots", label: "1. Add & Watch Folders", tag: "Roots" },
      { id: "processing-jobs", label: "2. Processing Pipelines", tag: "DAG" },
      { id: "storage-backup", label: "3. Archive & Export", tag: ".arova" },
    ],
  },
  {
    name: "Intelligence & AI",
    items: [
      { id: "hybrid-search", label: "Search & Ask Archive", tag: "RAG" },
      { id: "privacy-ai", label: "Privacy & BYO-AI", tag: "Gateway" },
    ],
  },
  {
    name: "Developer Tools",
    items: [
      { id: "mcp-config", label: "MCP Agent Server", tag: "Protocol" },
      { id: "database-explorer", label: "Database Explorer", tag: "SQLite" },
      { id: "system", label: "Engine Telemetry & Health", tag: "Core" },
    ],
  },
];

export function App() {
  const [activeSection, setActiveSection] = useState<NavSection>("overview");
  const [selectedVideoId, setSelectedVideoId] = useState<string | undefined>(undefined);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState<boolean>(true);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  const checkHealth = useCallback(async (signal?: AbortSignal) => {
    setChecking(true);
    try {
      const data = await fetchHealth(signal);
      setHealth(data);
      setError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setHealth(null);
      setError(err instanceof Error ? err.message : "Connection refused");
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void checkHealth(controller.signal);
    return () => controller.abort();
  }, [checkHealth]);

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const isOnline = health?.status === "ok" && !error;

  const currentLabel =
    NAV_GROUPS.flatMap((g) => g.items).find((item) => item.id === activeSection)?.label ??
    "Workstation";

  const commandItems: CommandItem[] = [
    ...NAV_GROUPS.flatMap((g) =>
      g.items.map((item) => ({
        id: `nav-${item.id}`,
        title: item.label,
        subtitle: `Jump to ${g.name} â†’ ${item.label}`,
        category: "Navigation" as const,
        onSelect: () => setActiveSection(item.id),
      }))
    ),
    {
      id: "act-import-media",
      title: "Index Local Media",
      subtitle: "Open media ingest console",
      category: "Action",
      shortcut: "Ctrl+I",
      onSelect: () => setActiveSection("overview"),
    },
    {
      id: "act-search",
      title: "Run Hybrid Semantic Search",
      subtitle: "Dense + BM25 Reciprocal Rank Fusion",
      category: "Action",
      shortcut: "/",
      onSelect: () => setActiveSection("hybrid-search"),
    },
    {
      id: "act-sync-health",
      title: "Probe Health & Telemetry",
      subtitle: "Execute live HTTP check against /api/v1/health",
      category: "Action",
      onSelect: () => void checkHealth(),
    },
  ];

  return (
    <div className="min-h-screen flex bg-[#080B12] text-[#F5F7FB] font-sans selection:bg-[#9B8CFF]/30 selection:text-white">
      {/* Docked Sidebar Navigation */}
      <aside className="w-64 border-r border-[#243149] bg-[#0B1019] flex flex-col justify-between p-4 shrink-0 h-screen sticky top-0 z-30 select-none">
        <div className="space-y-5 overflow-y-auto pr-1">
          {/* Brand Header */}
          <div className="flex items-center gap-2.5 pb-2 border-b border-[#243149]/60">
            <div className="h-8 w-8 rounded-control bg-[#172235] border border-[#243149] flex items-center justify-center shadow-sm shrink-0">
              <span className="font-mono font-bold text-[#9B8CFF] text-sm">A</span>
            </div>
            <div className="truncate min-w-0">
              <h1 className="text-xs font-semibold tracking-tight text-[#F5F7FB] truncate">
                Arova Intelligence
              </h1>
              <p className="text-[10px] font-mono text-[#A2AEC0] truncate">
                Cinematic Instrument
              </p>
            </div>
          </div>

          {/* Quick Command Palette Launcher */}
          <button
            type="button"
            onClick={() => setIsCommandPaletteOpen(true)}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-control bg-[#111827] hover:bg-[#172235] border border-[#243149] text-xs font-mono text-slate-400 transition-colors"
          >
            <span>Command Palette...</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#080B12] border border-[#243149] text-[#9B8CFF]">
              Ctrl+K
            </span>
          </button>

          {/* Grouped Navigation Sections */}
          <nav aria-label="Workstation Navigation" className="space-y-4">
            {NAV_GROUPS.map((group) => (
              <div key={group.name} className="space-y-1">
                <div className="px-2 text-[10px] font-mono text-slate-500 uppercase tracking-wider font-semibold">
                  {group.name}
                </div>
                {group.items.map((item) => {
                  const active = activeSection === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setActiveSection(item.id)}
                      className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-control text-xs transition-colors focus-visible:outline-none ${
                        active
                          ? "bg-[#172235] text-white font-medium border border-[#9B8CFF]/50 shadow-sm"
                          : "text-[#A2AEC0] hover:text-white hover:bg-[#111827]"
                      }`}
                    >
                      <span className="truncate pr-1">{item.label}</span>
                      <span
                        className={`text-[9px] font-mono px-1 rounded shrink-0 ${
                          active
                            ? "bg-[#080B12] text-[#9B8CFF] border border-[#243149]"
                            : "text-slate-600"
                        }`}
                      >
                        {item.tag}
                      </span>
                    </button>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        {/* Sidebar Status Hub */}
        <div className="space-y-2 pt-3 border-t border-[#243149] text-xs">
          <div
            data-testid="health-badge"
            className="p-2.5 rounded-panel border border-[#243149] bg-[#111827] space-y-1"
          >
            <div className="flex items-center justify-between">
              <span className="text-slate-300 font-medium text-xs">FastAPI Engine</span>
              <span className="inline-flex items-center gap-1.5 font-mono text-[11px]">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    checking
                      ? "bg-[#F4BF69] animate-ping"
                      : isOnline
                      ? "bg-[#51DCC8]"
                      : "bg-[#FF7386]"
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
            {error && <p className="text-[#FF7386] font-mono text-[11px] truncate">{error}</p>}
          </div>
        </div>
      </aside>

      {/* Main Full-Screen Workstation Canvas */}
      <main className="flex-1 min-w-0 h-screen overflow-y-auto flex flex-col">
        {/* Studio Top Bar */}
        <header className="h-14 border-b border-[#243149] bg-[#0B1019]/90 backdrop-blur px-6 flex items-center justify-between shrink-0 sticky top-0 z-20">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-xs font-semibold text-[#F5F7FB] truncate">{currentLabel}</span>
            <span className="text-slate-600">/</span>
            <span className="text-[11px] font-mono text-[#A2AEC0] hidden sm:inline truncate">
              Local-First Multimodal Creator Instrument
            </span>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#111827] border border-[#243149] text-[#51DCC8]">
              Local Enclave Active
            </span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#111827] border border-[#243149] text-slate-400">
              Remote AI: Consented Only
            </span>
            <button
              type="button"
              onClick={() => void checkHealth()}
              disabled={checking}
              className="px-2.5 py-1 rounded-control bg-[#172235] hover:bg-[#232f48] text-[11px] font-mono text-slate-200 border border-[#243149] transition-colors disabled:opacity-50"
            >
              {checking ? "Checking..." : "Sync Health"}
            </button>
          </div>
        </header>

        {/* View Router Content Area */}
        <div className="flex-1 p-6 lg:p-8 w-full max-w-[1920px] mx-auto">
          <ErrorBoundary fallbackTitle="Workstation View Enclave">
            {activeSection === "overview" ? (
              <OverviewView
                onNavigate={(s) => setActiveSection(s as NavSection)}
                onSelectVideo={(vId) => {
                  setSelectedVideoId(vId);
                  setActiveSection("workstation");
                }}
              />
            ) : activeSection === "media-library" ? (
              <MediaLibraryView onNavigate={(s) => setActiveSection(s as NavSection)} />
            ) : activeSection === "workstation" ? (
              <VideoWorkstationView initialVideoId={selectedVideoId} />
            ) : activeSection === "hybrid-search" ? (
              <HybridSearchView />
            ) : activeSection === "discovery-roots" ? (
              <DiscoverySourcesView onNavigate={(s) => setActiveSection(s as NavSection)} />
            ) : activeSection === "processing-jobs" ? (
              <ProcessingJobsView />
            ) : activeSection === "privacy-ai" ? (
              <PrivacyAiView />
            ) : activeSection === "storage-backup" ? (
              <StorageBackupView />
            ) : activeSection === "mcp-config" ? (
              <McpConfigView />
            ) : activeSection === "database-explorer" ? (
              <DatabaseExplorerView />
            ) : activeSection === "system" ? (
              <SystemHealthView
                health={health}
                checking={checking}
                error={error}
                onRefresh={() => void checkHealth()}
              />
            ) : null}
          </ErrorBoundary>
        </div>
      </main>

      {/* Global Command Palette Modal */}
      <CommandPaletteModal
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        commands={commandItems}
      />
    </div>
  );
}

export default App;

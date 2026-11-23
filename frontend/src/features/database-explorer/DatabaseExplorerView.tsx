import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiHttpError,
  fetchDatabaseMigrations,
  fetchDatabaseOverview,
  fetchDatabaseRelationships,
  fetchDatabaseTables,
  fetchTableDetails,
  fetchTableRows,
  type DatabaseOverview,
  type DatabaseRelationships,
  type MigrationRevision,
  type TableDetails,
  type TableRowsResponse,
  type TableSummary,
} from "../../services/api";
import { SchemaRelationshipDiagram } from "./SchemaRelationshipDiagram";

type TabMode = "overview" | "tables" | "structure" | "rows" | "migrations" | "relationships";
type ExplorerAuthState = "locked" | "loading" | "ready" | "unauthorized" | "failed";

function formatCellPreview(val: unknown): string {
  if (val === null || val === undefined) return "NULL";
  if (typeof val === "object") {
    try {
      return JSON.stringify(val, null, 2);
    } catch {
      return String(val);
    }
  }
  return String(val);
}

export function DatabaseExplorerView() {
  const [token, setToken] = useState<string>(() => sessionStorage.getItem("arova_admin_token") || "");
  const [inputToken, setInputToken] = useState<string>(token);
  const [activeTab, setActiveTab] = useState<TabMode>("overview");

  // Data state
  const [overview, setOverview] = useState<DatabaseOverview | null>(null);
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>("videos");
  const [tableDetails, setTableDetails] = useState<TableDetails | null>(null);
  const [tableRows, setTableRows] = useState<TableRowsResponse | null>(null);
  const [migrations, setMigrations] = useState<MigrationRevision[]>([]);
  const [relationships, setRelationships] = useState<DatabaseRelationships | null>(null);
  const [inspectedCell, setInspectedCell] = useState<{ column: string; value: string } | null>(null);

  // Client-side table filters & pagination
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [rowOffset, setRowOffset] = useState<number>(0);
  const rowLimit = 50;

  // Explicit state machine
  const [authState, setAuthState] = useState<ExplorerAuthState>(() => (token ? "loading" : "locked"));
  const [tabLoading, setTabLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<number | null>(null);

  const clearLoadedData = useCallback(() => {
    setOverview(null);
    setTables([]);
    setTableDetails(null);
    setTableRows(null);
    setMigrations([]);
    setRelationships(null);
    setInspectedCell(null);
  }, []);

  const handleError = useCallback(
    (err: unknown, fallback: string) => {
      if (err instanceof DOMException && err.name === "AbortError") return;
      if (err instanceof ApiHttpError) {
        setErrorCode(err.status);
        if (err.status === 401) {
          clearLoadedData();
          setAuthState("unauthorized");
          setError(err.message);
          return;
        }
        setAuthState("failed");
        setError(err.message);
        return;
      }
      setErrorCode(null);
      setAuthState("failed");
      setError(err instanceof Error ? err.message : fallback);
    },
    [clearLoadedData]
  );

  const handleAuthenticate = (e?: FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputToken.trim();
    setError(null);
    setErrorCode(null);
    if (!trimmed) {
      setToken("");
      clearLoadedData();
      setAuthState("locked");
      sessionStorage.removeItem("arova_admin_token");
      return;
    }
    sessionStorage.setItem("arova_admin_token", trimmed);
    try {
      localStorage.removeItem("arova_admin_token");
    } catch {
      // Ignore restricted storage
    }
    setToken(trimmed);
  };

  const handleLock = () => {
    sessionStorage.removeItem("arova_admin_token");
    try {
      localStorage.removeItem("arova_admin_token");
    } catch {
      // Ignore restricted storage
    }
    setToken("");
    setInputToken("");
    clearLoadedData();
    setError(null);
    setErrorCode(null);
    setAuthState("locked");
  };

  // Load overview & full table catalog ONLY on token change or explicit refresh (never on table click or typing)
  const loadOverviewAndTables = useCallback(
    async (signal?: AbortSignal) => {
      if (!token) {
        setAuthState("locked");
        return;
      }
      setAuthState("loading");
      setError(null);
      setErrorCode(null);
      try {
        const [ov, tbls] = await Promise.all([
          fetchDatabaseOverview(token, signal),
          fetchDatabaseTables(token, undefined, undefined, signal),
        ]);
        if (signal?.aborted) return;
        setOverview(ov);
        setTables(tbls);
        setSelectedTable((prev) =>
          tbls.length > 0 && tbls.some((t) => t.name === prev)
            ? prev
            : tbls.find((t) => t.name === "videos")?.name ?? tbls[0]?.name ?? ""
        );
        setAuthState("ready");
      } catch (err) {
        handleError(err, "Failed to connect to Database Explorer API");
      }
    },
    [token, handleError]
  );

  useEffect(() => {
    if (!token) {
      setAuthState("locked");
      return;
    }
    const controller = new AbortController();
    void loadOverviewAndTables(controller.signal);
    return () => controller.abort();
  }, [token, loadOverviewAndTables]);

  // Tab-specific lazy loaders with AbortController cleanup
  useEffect(() => {
    if (!token || authState !== "ready") return;
    const controller = new AbortController();

    async function loadTab() {
      setTabLoading(true);
      setError(null);
      try {
        if (activeTab === "structure" && selectedTable) {
          const details = await fetchTableDetails(token, selectedTable, controller.signal);
          if (!controller.signal.aborted) setTableDetails(details);
        } else if (activeTab === "rows" && selectedTable) {
          const rowsData = await fetchTableRows(
            token,
            selectedTable,
            rowLimit,
            rowOffset,
            controller.signal
          );
          if (!controller.signal.aborted) {
            setTableRows(rowsData);
            setInspectedCell(null);
          }
        } else if (activeTab === "migrations") {
          const data = await fetchDatabaseMigrations(token, controller.signal);
          if (!controller.signal.aborted) setMigrations(data);
        } else if (activeTab === "relationships") {
          const data = await fetchDatabaseRelationships(token, controller.signal);
          if (!controller.signal.aborted) setRelationships(data);
        }
      } catch (err) {
        handleError(err, `Failed to load ${activeTab}`);
      } finally {
        if (!controller.signal.aborted) setTabLoading(false);
      }
    }

    if (activeTab !== "overview" && activeTab !== "tables") {
      void loadTab();
    }
    return () => controller.abort();
  }, [token, authState, activeTab, selectedTable, rowOffset, handleError]);

  const filteredTables = useMemo(() => {
    const q = searchFilter.trim().toLowerCase();
    return tables.filter((t) => {
      if (categoryFilter && t.category !== categoryFilter) return false;
      if (q && !t.name.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [tables, searchFilter, categoryFilter]);

  const handleTableSelect = (name: string, targetTab: TabMode = "structure") => {
    setSelectedTable(name);
    setRowOffset(0);
    setInspectedCell(null);
    setActiveTab(targetTab);
  };

  const getCategoryBadgeClass = (category: string) => {
    switch (category) {
      case "application":
        return "bg-emerald-950 text-emerald-300 border-emerald-800";
      case "migration_metadata":
        return "bg-blue-950 text-blue-300 border-blue-800";
      case "fts5_shadow":
        return "bg-purple-950 text-purple-300 border-purple-800";
      case "internal":
        return "bg-amber-950 text-amber-300 border-amber-800";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const isLoading = authState === "loading" || tabLoading;

  return (
    <div className="space-y-6">
      {/* Header & Token Authentication Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-5 rounded-xl border border-[#243149] bg-[#111827] shadow-sm">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h2 className="text-lg font-semibold tracking-tight text-[#F5F7FB]">
              Live SQLite Database Explorer
            </h2>
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border border-emerald-800 bg-emerald-950/60 text-emerald-400">
              mode=ro · query_only=ON
            </span>
            <span
              data-testid="db-auth-status"
              className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${
                authState === "ready"
                  ? "border-[#51DCC8]/40 bg-[#51DCC8]/10 text-[#51DCC8]"
                  : authState === "unauthorized"
                  ? "border-rose-800 bg-rose-950/60 text-rose-300"
                  : authState === "failed"
                  ? "border-amber-800 bg-amber-950/60 text-amber-300"
                  : "border-[#243149] bg-[#0B1019] text-slate-400"
              }`}
            >
              {authState === "ready"
                ? "Authorized"
                : authState === "loading"
                ? "Connecting..."
                : authState === "unauthorized"
                ? "Unauthorized"
                : authState === "failed"
                ? "Unavailable"
                : "Locked"}
            </span>
          </div>
          <p className="text-xs text-[#A2AEC0] mt-1">
            Read-only schema introspection, paginated row inspection, and interactive SQLite
            foreign-key ER visualization.
          </p>
        </div>

        {/* Local Admin Token Form */}
        <form onSubmit={handleAuthenticate} className="flex flex-wrap items-center gap-2">
          <label htmlFor="db-admin-token-input" className="sr-only">
            Local Admin Bearer Token
          </label>
          <input
            id="db-admin-token-input"
            type="password"
            autoComplete="off"
            placeholder="Local Admin Bearer Token..."
            value={inputToken}
            onChange={(e) => setInputToken(e.target.value)}
            className="w-56 px-3 py-1.5 text-xs bg-[#080B12] border border-[#243149] rounded-lg text-[#F5F7FB] focus:outline-none focus:border-[#9B8CFF] font-mono"
          />
          <button
            type="submit"
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-[#9B8CFF] hover:bg-[#8b7aee] text-[#080B12] font-semibold transition"
          >
            Authenticate
          </button>
          {token && (
            <button
              type="button"
              onClick={handleLock}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-[#172235] hover:bg-[#232f48] text-slate-300 border border-[#243149] transition"
            >
              Lock
            </button>
          )}
          <button
            type="button"
            onClick={() => void loadOverviewAndTables()}
            disabled={isLoading || !token}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-800 hover:bg-emerald-700 text-white transition disabled:opacity-50"
          >
            {isLoading ? "Refreshing..." : "Refresh"}
          </button>
        </form>
      </div>

      {/* Explicit Locked / Unauthorized / Failed States */}
      {authState === "locked" && (
        <div
          data-testid="db-locked-panel"
          className="p-6 rounded-xl border border-[#243149] bg-[#111827] space-y-3"
        >
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-[#172235] text-[#9B8CFF] border border-[#9B8CFF]/40">
              LOCAL ADMIN AUTHENTICATION REQUIRED
            </span>
          </div>
          <h3 className="text-sm font-semibold text-[#F5F7FB]">
            Database Explorer is Locked
          </h3>
          <p className="text-xs text-[#A2AEC0] leading-relaxed max-w-2xl">
            For security, read-only SQLite introspection endpoints (
            <code className="text-[#51DCC8]">/api/v1/admin/database/*</code>) always require a valid
            local admin bearer token and trusted localhost Origin/Host headers.
          </p>
          <ol className="text-xs text-slate-300 space-y-1.5 list-decimal list-inside font-mono bg-[#0B1019] p-4 rounded-lg border border-[#243149]">
            <li>
              Set <code className="text-[#51DCC8]">ADMIN_AUTH_TOKEN</code> in your local{" "}
              <code className="text-slate-200">.env</code> (or restart the FastAPI backend with it
              in the environment).
            </li>
            <li>Paste the token into the Local Admin Bearer Token input above and press Enter.</li>
            <li>
              The token is stored only in this browser tab&apos;s{" "}
              <code className="text-slate-200">sessionStorage</code> and cleared when you click Lock.
            </li>
          </ol>
        </div>
      )}

      {authState === "unauthorized" && (
        <div
          role="alert"
          data-testid="db-unauthorized-panel"
          className="p-5 rounded-xl border border-rose-900/70 bg-rose-950/30 space-y-2"
        >
          <h3 className="text-sm font-semibold text-rose-300">
            Unauthorized (HTTP 401) — Invalid or Expired Admin Token
          </h3>
          <p className="text-xs text-rose-200/90 font-mono">{error}</p>
          <p className="text-xs text-slate-300">
            Verify that your token matches <code className="text-[#51DCC8]">ADMIN_AUTH_TOKEN</code>{" "}
            (or <code className="text-[#51DCC8]">API_AUTH_TOKEN</code>) configured for the running
            FastAPI server, then re-authenticate above.
          </p>
        </div>
      )}

      {authState === "failed" && error && (
        <div
          role="alert"
          data-testid="db-error-panel"
          className="p-5 rounded-xl border border-amber-900/70 bg-amber-950/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
        >
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-amber-300">
              Database Explorer Unavailable{errorCode ? ` (HTTP ${errorCode})` : ""}
            </h3>
            <p className="text-xs text-amber-200/90 font-mono">{error}</p>
            <p className="text-xs text-slate-300">
              Ensure the local FastAPI backend is reachable at{" "}
              <code className="text-[#51DCC8]">127.0.0.1:8000</code> and that this page&apos;s
              Origin is permitted in <code className="text-[#51DCC8]">CORS_ORIGINS</code>.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadOverviewAndTables()}
            className="px-3.5 py-1.5 text-xs font-mono rounded-lg bg-[#172235] hover:bg-[#232f48] text-white border border-[#243149] shrink-0"
          >
            Retry Connection
          </button>
        </div>
      )}

      {authState === "loading" && (
        <div className="p-8 rounded-xl border border-[#243149] bg-[#111827] text-center text-xs font-mono text-slate-400">
          Introspecting active SQLite schema in read-only mode...
        </div>
      )}

      {/* Authenticated Explorer Tabs & Views */}
      {authState === "ready" && (
        <>
          {error && (
            <div
              role="alert"
              className="p-3.5 rounded-xl border border-rose-900/60 bg-rose-950/40 text-rose-300 text-xs flex items-center justify-between"
            >
              <span>{error}</span>
              <button
                type="button"
                onClick={() => setError(null)}
                aria-label="Dismiss error"
                className="text-rose-400 hover:text-rose-200 text-sm"
              >
                ×
              </button>
            </div>
          )}

          {/* Explorer Navigation Tabs */}
          <div className="flex border-b border-[#243149] gap-1 overflow-x-auto" role="tablist">
            {(
              [
                { id: "overview", label: "Overview" },
                { id: "tables", label: `Tables (${tables.length})` },
                { id: "structure", label: "Table Structure" },
                { id: "rows", label: "Paginated Rows" },
                { id: "migrations", label: "Migration History" },
                { id: "relationships", label: "ER Relationships" },
              ] as const
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2.5 text-xs font-medium border-b-2 transition -mb-px whitespace-nowrap ${
                  activeTab === tab.id
                    ? "border-[#51DCC8] text-[#F5F7FB]"
                    : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab 1: Overview */}
          {activeTab === "overview" && overview && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl border border-[#243149] bg-[#111827]">
                  <span className="text-[11px] font-mono text-slate-400 uppercase">Engine &amp; Mode</span>
                  <p className="text-lg font-semibold text-[#F5F7FB] mt-1 capitalize">
                    {overview.engine}{" "}
                    <span className="text-xs text-[#51DCC8] font-mono">(Read-Only)</span>
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1 font-mono">{overview.database_name}</p>
                </div>
                <div className="p-4 rounded-xl border border-[#243149] bg-[#111827]">
                  <span className="text-[11px] font-mono text-slate-400 uppercase">Current Revision</span>
                  <p className="text-sm font-semibold text-[#F5F7FB] mt-1 font-mono truncate">
                    {overview.current_revision || "None"}
                  </p>
                  <p className="text-[11px] text-[#51DCC8] mt-1">Alembic Schema Version</p>
                </div>
                <div className="p-4 rounded-xl border border-[#243149] bg-[#111827]">
                  <span className="text-[11px] font-mono text-slate-400 uppercase">Table Distribution</span>
                  <p className="text-lg font-semibold text-[#F5F7FB] mt-1">
                    {overview.table_counts.application}{" "}
                    <span className="text-xs text-slate-400">/ {overview.table_counts.total} Total</span>
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {overview.table_counts.fts5_shadow} FTS5 · {overview.table_counts.internal} Internal
                  </p>
                </div>
                <div className="p-4 rounded-xl border border-[#243149] bg-[#111827]">
                  <span className="text-[11px] font-mono text-slate-400 uppercase">Integrity Check</span>
                  <p className="text-lg font-semibold text-[#51DCC8] mt-1 uppercase font-mono">
                    {overview.integrity_status}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    {(overview.file_size_bytes / 1024).toFixed(1)} KB DB Size
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-[#243149] bg-[#111827] p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[#F5F7FB]">
                    Application Tables &amp; Row Counts
                  </h3>
                  <button
                    type="button"
                    onClick={() => setActiveTab("relationships")}
                    className="px-3 py-1 text-xs font-mono rounded-lg bg-[#172235] hover:bg-[#232f48] text-[#9B8CFF] border border-[#9B8CFF]/40"
                  >
                    Open Visual ER Diagram →
                  </button>
                </div>
                {tables.filter((t) => t.category === "application").length === 0 ? (
                  <p className="text-xs font-mono text-slate-400 py-6 text-center">
                    No application tables found in this database.
                  </p>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                    {tables
                      .filter((t) => t.category === "application")
                      .map((t) => (
                        <button
                          key={t.name}
                          type="button"
                          onClick={() => handleTableSelect(t.name, "rows")}
                          className="text-left p-3 rounded-lg border border-[#243149] bg-[#0B1019] hover:border-[#9B8CFF]/60 transition"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-mono font-medium text-[#F5F7FB] truncate">
                              {t.name}
                            </span>
                            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-[#172235] text-[#51DCC8] shrink-0">
                              {t.row_count}
                            </span>
                          </div>
                          <p className="text-[10px] text-slate-400 mt-1 font-mono truncate">
                            {t.column_count} cols · PK: {t.primary_key.join(",") || "None"}
                          </p>
                        </button>
                      ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab 2: Tables List */}
          {activeTab === "tables" && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-3 justify-between items-center">
                <div className="flex items-center gap-3 w-full sm:w-auto">
                  <input
                    type="text"
                    placeholder="Filter tables..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                    className="px-3 py-1.5 text-xs bg-[#080B12] border border-[#243149] rounded-lg text-[#F5F7FB] focus:outline-none focus:border-[#9B8CFF] font-mono w-64"
                  />
                  <select
                    value={categoryFilter}
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    className="px-3 py-1.5 text-xs bg-[#080B12] border border-[#243149] rounded-lg text-slate-300 focus:outline-none focus:border-[#9B8CFF]"
                  >
                    <option value="">All Categories</option>
                    <option value="application">Application Tables</option>
                    <option value="migration_metadata">Migration Metadata</option>
                    <option value="fts5_shadow">FTS5 Shadow Tables</option>
                    <option value="internal">SQLite Internal</option>
                  </select>
                </div>
                <span className="text-xs text-slate-400 font-mono">
                  Showing {filteredTables.length} of {tables.length} tables
                </span>
              </div>

              <div className="rounded-xl border border-[#243149] bg-[#111827] overflow-x-auto">
                {filteredTables.length === 0 ? (
                  <div className="p-8 text-center text-xs font-mono text-slate-400">
                    No tables match the current filter.
                  </div>
                ) : (
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-[#0B1019] text-slate-400 uppercase font-mono text-[10px] border-b border-[#243149]">
                      <tr>
                        <th className="px-4 py-3">Table Name</th>
                        <th className="px-4 py-3">Category</th>
                        <th className="px-4 py-3">Rows</th>
                        <th className="px-4 py-3">Columns</th>
                        <th className="px-4 py-3">Primary Key</th>
                        <th className="px-4 py-3">Foreign Keys</th>
                        <th className="px-4 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#243149]">
                      {filteredTables.map((t) => (
                        <tr key={t.name} className="hover:bg-[#172235]/50 transition font-mono">
                          <td className="px-4 py-3 font-semibold text-[#F5F7FB]">{t.name}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] border ${getCategoryBadgeClass(
                                t.category
                              )}`}
                            >
                              {t.category}
                            </span>
                          </td>
                          <td className="px-4 py-3">{t.row_count}</td>
                          <td className="px-4 py-3">{t.column_count}</td>
                          <td className="px-4 py-3 text-slate-400">
                            {t.primary_key.join(", ") || "None"}
                          </td>
                          <td className="px-4 py-3">
                            {t.has_foreign_keys ? (
                              <span className="text-[#51DCC8]">{t.foreign_key_count} FKs</span>
                            ) : (
                              <span className="text-slate-500">None</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                            <button
                              type="button"
                              onClick={() => handleTableSelect(t.name, "structure")}
                              className="px-2.5 py-1 text-[11px] rounded bg-[#172235] hover:bg-[#232f48] text-slate-200 transition"
                            >
                              Structure
                            </button>
                            <button
                              type="button"
                              onClick={() => handleTableSelect(t.name, "rows")}
                              className="px-2.5 py-1 text-[11px] rounded bg-emerald-900/60 hover:bg-emerald-800 text-emerald-300 transition"
                            >
                              Rows ({t.row_count})
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {/* Tab 3: Structure Inspector */}
          {activeTab === "structure" && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 uppercase font-mono">Selected Table:</span>
                  <select
                    value={selectedTable}
                    onChange={(e) => handleTableSelect(e.target.value, "structure")}
                    className="px-3 py-1.5 text-xs bg-[#080B12] border border-[#243149] rounded-lg text-[#F5F7FB] focus:outline-none focus:border-[#9B8CFF] font-mono"
                  >
                    {tables.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name} ({t.category})
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  onClick={() => handleTableSelect(selectedTable, "rows")}
                  disabled={!selectedTable}
                  className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-800 hover:bg-emerald-700 text-white transition disabled:opacity-50"
                >
                  View Table Rows →
                </button>
              </div>

              {tabLoading && !tableDetails ? (
                <div className="p-8 rounded-xl border border-[#243149] bg-[#111827] text-center text-xs font-mono text-slate-400">
                  Loading schema structure for {selectedTable}...
                </div>
              ) : tableDetails ? (
                <div className="space-y-6">
                  <div className="rounded-xl border border-[#243149] bg-[#111827] overflow-x-auto">
                    <div className="px-4 py-3 bg-[#0B1019] border-b border-[#243149] flex justify-between items-center">
                      <h4 className="text-xs font-semibold text-slate-200 uppercase font-mono tracking-wider">
                        Columns ({tableDetails.columns.length})
                      </h4>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] border ${getCategoryBadgeClass(
                          tableDetails.category
                        )}`}
                      >
                        {tableDetails.category}
                      </span>
                    </div>
                    <table className="w-full text-left text-xs text-slate-300 font-mono">
                      <thead className="bg-[#111827] text-slate-400 uppercase text-[10px] border-b border-[#243149]">
                        <tr>
                          <th className="px-4 py-2.5">Name</th>
                          <th className="px-4 py-2.5">Type</th>
                          <th className="px-4 py-2.5">Nullable</th>
                          <th className="px-4 py-2.5">Primary Key</th>
                          <th className="px-4 py-2.5">Default Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#243149]">
                        {tableDetails.columns.map((c) => (
                          <tr key={c.name} className="hover:bg-[#172235]/50 transition">
                            <td className="px-4 py-2.5 font-semibold text-[#F5F7FB] flex items-center gap-2">
                              {c.name}
                              {c.primary_key && (
                                <span className="px-1.5 py-0.5 rounded text-[9px] bg-amber-950 text-amber-300 border border-amber-800">
                                  PK
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 text-[#51DCC8]">{c.type}</td>
                            <td className="px-4 py-2.5 text-slate-400">{c.nullable ? "YES" : "NO"}</td>
                            <td className="px-4 py-2.5">{c.primary_key ? "YES" : "NO"}</td>
                            <td className="px-4 py-2.5 text-slate-400">{c.default ?? "NULL"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-xl border border-[#243149] bg-[#111827] p-4">
                      <h4 className="text-xs font-semibold text-slate-200 uppercase font-mono tracking-wider mb-3">
                        Foreign Keys ({tableDetails.foreign_keys.length})
                      </h4>
                      {tableDetails.foreign_keys.length === 0 ? (
                        <p className="text-xs text-slate-500 font-mono">No foreign keys defined</p>
                      ) : (
                        <ul className="space-y-2 text-xs font-mono">
                          {tableDetails.foreign_keys.map((fk, idx) => (
                            <li key={idx} className="p-2.5 rounded bg-[#0B1019] border border-[#243149]">
                              <span className="text-slate-300 font-medium">
                                {fk.constrained_columns.join(", ")}
                              </span>
                              <span className="text-slate-500 mx-2">→</span>
                              <button
                                type="button"
                                onClick={() => handleTableSelect(fk.referred_table, "structure")}
                                className="text-[#51DCC8] hover:underline font-medium"
                              >
                                {fk.referred_table} ({fk.referred_columns.join(", ")})
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>

                    <div className="rounded-xl border border-[#243149] bg-[#111827] p-4">
                      <h4 className="text-xs font-semibold text-slate-200 uppercase font-mono tracking-wider mb-3">
                        Indexes &amp; Unique Constraints (
                        {tableDetails.indexes.length + tableDetails.unique_constraints.length})
                      </h4>
                      {tableDetails.indexes.length + tableDetails.unique_constraints.length === 0 ? (
                        <p className="text-xs text-slate-500 font-mono">No secondary indexes defined</p>
                      ) : (
                        <ul className="space-y-2 text-xs font-mono">
                          {tableDetails.indexes.map((idx, i) => (
                            <li
                              key={i}
                              className="p-2.5 rounded bg-[#0B1019] border border-[#243149] flex justify-between"
                            >
                              <div>
                                <span className="text-slate-300 font-medium">
                                  {idx.name || "Unnamed Index"}
                                </span>
                                <p className="text-[11px] text-slate-400">
                                  {idx.column_names.join(", ")}
                                </p>
                              </div>
                              {idx.unique && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-950 text-blue-300 border border-blue-800 h-fit">
                                  UNIQUE
                                </span>
                              )}
                            </li>
                          ))}
                          {tableDetails.unique_constraints.map((uq, i) => (
                            <li
                              key={`uq-${i}`}
                              className="p-2.5 rounded bg-[#0B1019] border border-[#243149] flex justify-between"
                            >
                              <div>
                                <span className="text-slate-300 font-medium">
                                  {uq.name || "Unique Constraint"}
                                </span>
                                <p className="text-[11px] text-slate-400">
                                  {uq.column_names.join(", ")}
                                </p>
                              </div>
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-950 text-blue-300 border border-blue-800 h-fit">
                                UNIQUE
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {/* Tab 4: Paginated Rows View */}
          {activeTab === "rows" && (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row justify-between items-center gap-3">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 uppercase font-mono">Viewing Table:</span>
                  <select
                    value={selectedTable}
                    onChange={(e) => handleTableSelect(e.target.value, "rows")}
                    className="px-3 py-1.5 text-xs bg-[#080B12] border border-[#243149] rounded-lg text-[#F5F7FB] focus:outline-none focus:border-[#9B8CFF] font-mono"
                  >
                    {tables.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name} ({t.row_count} rows)
                      </option>
                    ))}
                  </select>
                </div>

                {tableRows && (
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 font-mono">
                      {tableRows.total === 0
                        ? "0 records"
                        : `${tableRows.offset + 1}–${Math.min(
                            tableRows.offset + tableRows.rows.length,
                            tableRows.total
                          )} of ${tableRows.total}`}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        disabled={tableRows.offset === 0}
                        onClick={() => setRowOffset((prev) => Math.max(0, prev - rowLimit))}
                        className="px-3 py-1 text-xs rounded bg-[#172235] hover:bg-[#232f48] disabled:opacity-40 text-slate-200 transition"
                      >
                        ← Prev
                      </button>
                      <button
                        type="button"
                        disabled={!tableRows.has_more}
                        onClick={() => setRowOffset((prev) => prev + rowLimit)}
                        className="px-3 py-1 text-xs rounded bg-[#172235] hover:bg-[#232f48] disabled:opacity-40 text-slate-200 transition"
                      >
                        Next →
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {tabLoading && !tableRows ? (
                <div className="p-8 rounded-xl border border-[#243149] bg-[#111827] text-center text-xs font-mono text-slate-400">
                  Loading paginated rows for {selectedTable}...
                </div>
              ) : tableRows ? (
                <div className="space-y-3">
                  <div className="rounded-xl border border-[#243149] bg-[#111827] overflow-hidden">
                    {tableRows.rows.length === 0 ? (
                      <div className="p-12 text-center text-slate-400 font-mono text-xs">
                        0 records found in table &quot;{tableRows.table_name}&quot;.
                      </div>
                    ) : (
                      <div className="overflow-x-auto max-h-[560px]">
                        <table className="w-full text-left text-xs text-slate-300 font-mono">
                          <thead className="bg-[#0B1019] text-slate-400 uppercase text-[10px] border-b border-[#243149] sticky top-0">
                            <tr>
                              {tableRows.columns.map((col) => (
                                <th key={col.name} className="px-4 py-3 whitespace-nowrap">
                                  <span className="text-[#F5F7FB]">{col.name}</span>
                                  <span className="block text-[9px] text-slate-500 font-normal">
                                    {col.type}
                                  </span>
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#243149]">
                            {tableRows.rows.map((row, rIdx) => (
                              <tr key={rIdx} className="hover:bg-[#172235]/50 transition">
                                {tableRows.columns.map((col) => {
                                  const val = row[col.name];
                                  const display = formatCellPreview(val);
                                  return (
                                    <td
                                      key={col.name}
                                      onClick={() =>
                                        setInspectedCell({ column: col.name, value: display })
                                      }
                                      title="Click to inspect full value"
                                      className="px-4 py-2.5 whitespace-nowrap max-w-xs truncate cursor-pointer"
                                    >
                                      {val === null || val === undefined ? (
                                        <span className="text-slate-600">NULL</span>
                                      ) : typeof val === "string" && val === "[REDACTED]" ? (
                                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-950 text-amber-300 border border-amber-800">
                                          [REDACTED]
                                        </span>
                                      ) : typeof val === "string" && val.startsWith("<BLOB ") ? (
                                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-purple-950 text-purple-300 border border-purple-800">
                                          {val}
                                        </span>
                                      ) : (
                                        display
                                      )}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {inspectedCell && (
                    <div className="p-3.5 rounded-xl border border-[#243149] bg-[#0B1019] space-y-1.5">
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span className="text-[#9B8CFF]">Cell Preview: {inspectedCell.column}</span>
                        <button
                          type="button"
                          onClick={() => setInspectedCell(null)}
                          className="text-slate-400 hover:text-white"
                        >
                          Close
                        </button>
                      </div>
                      <pre className="text-xs font-mono text-slate-200 whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                        {inspectedCell.value}
                      </pre>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}

          {/* Tab 5: Migration History */}
          {activeTab === "migrations" && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl border border-[#243149] bg-[#111827] flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-[#F5F7FB]">Alembic Migration History</h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Sequential schema revisions managed under forward-compatible migrations.
                  </p>
                </div>
                <span className="text-xs font-mono text-[#51DCC8] px-3 py-1 rounded border border-[#51DCC8]/40 bg-[#51DCC8]/10">
                  {migrations.length} Revisions Recorded
                </span>
              </div>

              <div className="rounded-xl border border-[#243149] bg-[#111827] divide-y divide-[#243149]">
                {migrations.length === 0 ? (
                  <div className="p-8 text-center text-xs font-mono text-slate-400">
                    {tabLoading ? "Loading migration history..." : "No migrations recorded."}
                  </div>
                ) : (
                  migrations.map((m, idx) => (
                    <div key={m.revision} className="p-4 flex items-center justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-mono font-bold text-[#F5F7FB]">
                            {m.revision}
                          </span>
                          {m.is_current && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-800">
                              CURRENT HEAD
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-300">{m.description}</p>
                        <p className="text-[11px] font-mono text-slate-500">
                          Down revision: {m.down_revision ?? "None (base)"}
                        </p>
                      </div>
                      <span className="text-xs font-mono text-slate-400">Step {idx + 1}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Tab 6: Interactive ER Relationships Visualization */}
          {activeTab === "relationships" &&
            (relationships ? (
              <SchemaRelationshipDiagram
                data={relationships}
                onInspectTable={(tbl, targetTab) => handleTableSelect(tbl, targetTab)}
              />
            ) : (
              <div className="p-8 rounded-xl border border-[#243149] bg-[#111827] text-center text-xs font-mono text-slate-400">
                Loading Entity-Relationship schema graph...
              </div>
            ))}
        </>
      )}
    </div>
  );
}

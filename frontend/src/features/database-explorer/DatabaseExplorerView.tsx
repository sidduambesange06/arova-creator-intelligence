import { useCallback, useEffect, useState } from "react";
import {
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

type TabMode = "overview" | "tables" | "structure" | "rows" | "migrations" | "relationships";

export function DatabaseExplorerView() {
  const [token, setToken] = useState<string>(() => sessionStorage.getItem("arova_admin_token") || "");
  const [inputToken, setInputToken] = useState<string>(token);
  const [activeTab, setActiveTab] = useState<TabMode>("overview");

  // State
  const [overview, setOverview] = useState<DatabaseOverview | null>(null);
  const [tables, setTables] = useState<TableSummary[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>("videos");
  const [tableDetails, setTableDetails] = useState<TableDetails | null>(null);
  const [tableRows, setTableRows] = useState<TableRowsResponse | null>(null);
  const [migrations, setMigrations] = useState<MigrationRevision[]>([]);
  const [relationships, setRelationships] = useState<DatabaseRelationships | null>(null);

  // Filters & Pagination
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [rowOffset, setRowOffset] = useState<number>(0);
  const rowLimit = 50;

  // Status
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const saveToken = () => {
    const trimmed = inputToken.trim();
    setToken(trimmed);
    if (trimmed) {
      sessionStorage.setItem("arova_admin_token", trimmed);
    } else {
      sessionStorage.removeItem("arova_admin_token");
    }
    // Clean up any historical persistent token from localStorage
    try {
      localStorage.removeItem("arova_admin_token");
    } catch {
      // Ignore in restricted storage environments
    }
  };

  // Load Overview & Tables
  const loadDatabaseData = useCallback(async () => {
    if (!token) {
      setError("Local Admin Bearer Token is required to inspect the database.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [ov, tbls] = await Promise.all([
        fetchDatabaseOverview(token),
        fetchDatabaseTables(token, searchFilter, categoryFilter),
      ]);
      setOverview(ov);
      setTables(tbls);
      if (tbls.length > 0 && !tbls.some((t) => t.name === selectedTable)) {
        setSelectedTable(tbls[0].name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect to Database Explorer API");
    } finally {
      setLoading(false);
    }
  }, [token, searchFilter, categoryFilter, selectedTable]);

  // Load Specific Table Details
  const loadSelectedTableDetails = useCallback(async (tableName: string) => {
    if (!token || !tableName) return;
    try {
      const details = await fetchTableDetails(token, tableName);
      setTableDetails(details);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to load details for ${tableName}`);
    }
  }, [token]);

  // Load Specific Table Rows
  const loadSelectedTableRows = useCallback(async (tableName: string, offset: number) => {
    if (!token || !tableName) return;
    setLoading(true);
    try {
      const rowsData = await fetchTableRows(token, tableName, rowLimit, offset);
      setTableRows(rowsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to load rows for ${tableName}`);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Load Migrations
  const loadMigrations = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchDatabaseMigrations(token);
      setMigrations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load migration history");
    }
  }, [token]);

  // Load Relationships
  const loadRelationships = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchDatabaseRelationships(token);
      setRelationships(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load relationships");
    }
  }, [token]);

  useEffect(() => {
    if (token) {
      void loadDatabaseData();
    }
  }, [token, loadDatabaseData]);

  useEffect(() => {
    if (token && selectedTable) {
      if (activeTab === "structure") {
        void loadSelectedTableDetails(selectedTable);
      } else if (activeTab === "rows") {
        void loadSelectedTableRows(selectedTable, rowOffset);
      }
    }
  }, [token, selectedTable, activeTab, rowOffset, loadSelectedTableDetails, loadSelectedTableRows]);

  useEffect(() => {
    if (token) {
      if (activeTab === "migrations") {
        void loadMigrations();
      } else if (activeTab === "relationships") {
        void loadRelationships();
      }
    }
  }, [token, activeTab, loadMigrations, loadRelationships]);

  const handleTableSelect = (name: string, targetTab: TabMode = "structure") => {
    setSelectedTable(name);
    setRowOffset(0);
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

  return (
    <div className="space-y-6">
      {/* Header & Token Authentication Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-xl border border-[#172338] bg-[#090e18] shadow-sm">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight text-slate-100">
              Live SQLite Database Explorer
            </h2>
            <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border border-emerald-800 bg-emerald-950/60 text-emerald-400">
              mode=ro · query_only=ON
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Read-only schema introspection, row inspection, and relational mapping under SQLite WAL containment.
          </p>
        </div>

        {/* Local Admin Token Input */}
        <div className="flex items-center gap-2">
          <div className="relative">
            <input
              type="password"
              placeholder="Admin Bearer Token..."
              value={inputToken}
              onChange={(e) => setInputToken(e.target.value)}
              className="w-56 px-3 py-1.5 text-xs bg-[#060911] border border-[#172338] rounded-lg text-slate-100 focus:outline-none focus:border-slate-500 font-mono"
            />
          </div>
          <button
            onClick={saveToken}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
          >
            Authenticate
          </button>
          <button
            onClick={() => void loadDatabaseData()}
            disabled={loading || !token}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-800 hover:bg-emerald-700 text-white transition disabled:opacity-50"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl border border-red-900/60 bg-red-950/40 text-red-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-200 text-sm">
            ✕
          </button>
        </div>
      )}

      {/* Explorer Navigation Tabs */}
      <div className="flex border-b border-[#172338] gap-1 overflow-x-auto">
        {(
          [
            { id: "overview", label: "Overview" },
            { id: "tables", label: "Tables List" },
            { id: "structure", label: "Table Structure" },
            { id: "rows", label: "Paginated Rows" },
            { id: "migrations", label: "Migration History" },
            { id: "relationships", label: "ER Relationships" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-xs font-medium border-b-2 transition -mb-px whitespace-nowrap ${
              activeTab === tab.id
                ? "border-emerald-500 text-slate-100"
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
            <div className="p-4 rounded-xl border border-[#172338] bg-[#090e18]">
              <span className="text-[11px] font-mono text-slate-400 uppercase">Engine & Mode</span>
              <p className="text-lg font-semibold text-slate-100 mt-1 capitalize">
                {overview.engine} <span className="text-xs text-emerald-400 font-mono">(Read-Only)</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-1">PRAGMA query_only = ON</p>
            </div>
            <div className="p-4 rounded-xl border border-[#172338] bg-[#090e18]">
              <span className="text-[11px] font-mono text-slate-400 uppercase">Current Revision</span>
              <p className="text-lg font-semibold text-slate-100 mt-1 font-mono text-sm">
                {overview.current_revision || "None"}
              </p>
              <p className="text-[11px] text-emerald-400 mt-1">Alembic Head Stamped</p>
            </div>
            <div className="p-4 rounded-xl border border-[#172338] bg-[#090e18]">
              <span className="text-[11px] font-mono text-slate-400 uppercase">Table Distribution</span>
              <p className="text-lg font-semibold text-slate-100 mt-1">
                {overview.table_counts.application}{" "}
                <span className="text-xs text-slate-400">/ {overview.table_counts.total} Total</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                {overview.table_counts.fts5_shadow} FTS5 · {overview.table_counts.internal} Internal
              </p>
            </div>
            <div className="p-4 rounded-xl border border-[#172338] bg-[#090e18]">
              <span className="text-[11px] font-mono text-slate-400 uppercase">Integrity Check</span>
              <p className="text-lg font-semibold text-emerald-400 mt-1 uppercase font-mono">
                {overview.integrity_status}
              </p>
              <p className="text-[11px] text-slate-400 mt-1">
                {(overview.file_size_bytes / 1024).toFixed(1)} KB DB Size
              </p>
            </div>
          </div>

          {/* Application Tables Quick Summary */}
          <div className="rounded-xl border border-[#172338] bg-[#090e18] p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Application Tables & Row Counts</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {tables
                .filter((t) => t.category === "application")
                .map((t) => (
                  <div
                    key={t.name}
                    onClick={() => handleTableSelect(t.name, "rows")}
                    className="p-3 rounded-lg border border-[#172338] bg-[#060911] hover:border-slate-600 cursor-pointer transition"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-medium text-slate-200 truncate">{t.name}</span>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {t.row_count}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1 font-mono">
                      {t.column_count} cols · PK: {t.primary_key.join(",") || "None"}
                    </p>
                  </div>
                ))}
            </div>
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
                placeholder="Search tables..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="px-3 py-1.5 text-xs bg-[#060911] border border-[#172338] rounded-lg text-slate-100 focus:outline-none focus:border-slate-500 font-mono w-64"
              />
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="px-3 py-1.5 text-xs bg-[#060911] border border-[#172338] rounded-lg text-slate-300 focus:outline-none focus:border-slate-500"
              >
                <option value="">All Categories</option>
                <option value="application">Application Tables</option>
                <option value="migration_metadata">Migration Metadata</option>
                <option value="fts5_shadow">FTS5 Shadow Tables</option>
                <option value="internal">SQLite Internal</option>
              </select>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              Showing {tables.length} tables
            </span>
          </div>

          <div className="rounded-xl border border-[#172338] bg-[#090e18] overflow-hidden">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-[#0e1626] text-slate-400 uppercase font-mono text-[10px] border-b border-[#172338]">
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
              <tbody className="divide-y divide-[#172338]">
                {tables.map((t) => (
                  <tr key={t.name} className="hover:bg-[#0c1220] transition font-mono">
                    <td className="px-4 py-3 font-semibold text-slate-100">{t.name}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] border ${getCategoryBadgeClass(t.category)}`}>
                        {t.category}
                      </span>
                    </td>
                    <td className="px-4 py-3">{t.row_count}</td>
                    <td className="px-4 py-3">{t.column_count}</td>
                    <td className="px-4 py-3 text-slate-400">{t.primary_key.join(", ") || "None"}</td>
                    <td className="px-4 py-3">
                      {t.has_foreign_keys ? (
                        <span className="text-emerald-400">{t.foreign_key_count} FKs</span>
                      ) : (
                        <span className="text-slate-400">None</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => handleTableSelect(t.name, "structure")}
                        className="px-2.5 py-1 text-[11px] rounded bg-slate-800 hover:bg-slate-700 text-slate-200 transition"
                      >
                        Structure
                      </button>
                      <button
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
          </div>
        </div>
      )}

      {/* Tab 3: Structure Inspector */}
      {activeTab === "structure" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400 uppercase font-mono">Selected Table:</span>
              <select
                value={selectedTable}
                onChange={(e) => handleTableSelect(e.target.value, "structure")}
                className="px-3 py-1.5 text-xs bg-[#060911] border border-[#172338] rounded-lg text-slate-100 focus:outline-none focus:border-slate-500 font-mono"
              >
                {tables.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name} ({t.category})
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => handleTableSelect(selectedTable, "rows")}
              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-800 hover:bg-emerald-700 text-white transition"
            >
              View Table Rows →
            </button>
          </div>

          {tableDetails && (
            <div className="space-y-6">
              {/* Columns Table */}
              <div className="rounded-xl border border-[#172338] bg-[#090e18] overflow-hidden">
                <div className="px-4 py-3 bg-[#0e1626] border-b border-[#172338] flex justify-between items-center">
                  <h4 className="text-xs font-semibold text-slate-200 uppercase font-mono tracking-wider">
                    Columns ({tableDetails.columns.length})
                  </h4>
                  <span className={`px-2 py-0.5 rounded text-[10px] border ${getCategoryBadgeClass(tableDetails.category)}`}>
                    {tableDetails.category}
                  </span>
                </div>
                <table className="w-full text-left text-xs text-slate-300 font-mono">
                  <thead className="bg-[#090e18] text-slate-400 uppercase text-[10px] border-b border-[#172338]">
                    <tr>
                      <th className="px-4 py-2.5">Name</th>
                      <th className="px-4 py-2.5">Type</th>
                      <th className="px-4 py-2.5">Nullable</th>
                      <th className="px-4 py-2.5">Primary Key</th>
                      <th className="px-4 py-2.5">Default Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#172338]">
                    {tableDetails.columns.map((c) => (
                      <tr key={c.name} className="hover:bg-[#0c1220] transition">
                        <td className="px-4 py-2.5 font-semibold text-slate-100 flex items-center gap-2">
                          {c.name}
                          {c.primary_key && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-amber-950 text-amber-300 border border-amber-800">
                              PK
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-emerald-400">{c.type}</td>
                        <td className="px-4 py-2.5 text-slate-400">{c.nullable ? "YES" : "NO"}</td>
                        <td className="px-4 py-2.5">{c.primary_key ? "YES" : "NO"}</td>
                        <td className="px-4 py-2.5 text-slate-400">{c.default ?? "NULL"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Foreign Keys & Constraints */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Foreign Keys */}
                <div className="rounded-xl border border-[#172338] bg-[#090e18] p-4">
                  <h4 className="text-xs font-semibold text-slate-200 uppercase font-mono tracking-wider mb-3">
                    Foreign Keys ({tableDetails.foreign_keys.length})
                  </h4>
                  {tableDetails.foreign_keys.length === 0 ? (
                    <p className="text-xs text-slate-500 font-mono">No foreign keys defined</p>
                  ) : (
                    <ul className="space-y-2 text-xs font-mono">
                      {tableDetails.foreign_keys.map((fk, idx) => (
                        <li key={idx} className="p-2.5 rounded bg-[#060911] border border-[#172338]">
                          <span className="text-slate-300 font-medium">{fk.constrained_columns.join(", ")}</span>
                          <span className="text-slate-400 mx-2">→</span>
                          <span className="text-emerald-400 font-medium">
                            {fk.referred_table} ({fk.referred_columns.join(", ")})
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Indexes */}
                <div className="rounded-xl border border-[#172338] bg-[#090e18] p-4">
                  <h4 className="text-xs font-semibold text-slate-200 uppercase font-mono tracking-wider mb-3">
                    Indexes & Unique Constraints ({tableDetails.indexes.length + tableDetails.unique_constraints.length})
                  </h4>
                  <ul className="space-y-2 text-xs font-mono">
                    {tableDetails.indexes.map((idx, i) => (
                      <li key={i} className="p-2.5 rounded bg-[#060911] border border-[#172338] flex justify-between">
                        <div>
                          <span className="text-slate-300 font-medium">{idx.name || "Unnamed Index"}</span>
                          <p className="text-[11px] text-slate-400">{idx.column_names.join(", ")}</p>
                        </div>
                        {idx.unique && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-950 text-blue-300 border border-blue-800 h-fit">
                            UNIQUE
                          </span>
                        )}
                      </li>
                    ))}
                    {tableDetails.unique_constraints.map((uq, i) => (
                      <li key={`uq-${i}`} className="p-2.5 rounded bg-[#060911] border border-[#172338] flex justify-between">
                        <div>
                          <span className="text-slate-300 font-medium">{uq.name || "Unique Constraint"}</span>
                          <p className="text-[11px] text-slate-400">{uq.column_names.join(", ")}</p>
                        </div>
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-blue-950 text-blue-300 border border-blue-800 h-fit">
                          UNIQUE
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
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
                className="px-3 py-1.5 text-xs bg-[#060911] border border-[#172338] rounded-lg text-slate-100 focus:outline-none focus:border-slate-500 font-mono"
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
                    : `${tableRows.offset + 1}–${Math.min(tableRows.offset + tableRows.rows.length, tableRows.total)} of ${tableRows.total}`}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    disabled={tableRows.offset === 0}
                    onClick={() => setRowOffset((prev) => Math.max(0, prev - rowLimit))}
                    className="px-3 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 transition"
                  >
                    ← Prev
                  </button>
                  <button
                    disabled={!tableRows.has_more}
                    onClick={() => setRowOffset((prev) => prev + rowLimit)}
                    className="px-3 py-1 text-xs rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 transition"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </div>

          {tableRows && (
            <div className="rounded-xl border border-[#172338] bg-[#090e18] overflow-hidden">
              {tableRows.rows.length === 0 ? (
                <div className="p-12 text-center text-slate-500 font-mono text-xs">
                  0 records found in table "{tableRows.table_name}".
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[600px]">
                  <table className="w-full text-left text-xs text-slate-300 font-mono">
                    <thead className="bg-[#0e1626] text-slate-400 uppercase text-[10px] border-b border-[#172338] sticky top-0">
                      <tr>
                        {tableRows.columns.map((col) => (
                          <th key={col.name} className="px-4 py-3 whitespace-nowrap">
                            <span className="text-slate-200">{col.name}</span>
                            <span className="block text-[9px] text-slate-500 font-normal">{col.type}</span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#172338]">
                      {tableRows.rows.map((row, rIdx) => (
                        <tr key={rIdx} className="hover:bg-[#0c1220] transition">
                          {tableRows.columns.map((col) => {
                            const val = row[col.name];
                            return (
                              <td key={col.name} className="px-4 py-2.5 whitespace-nowrap max-w-xs truncate">
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
                                  String(val)
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
          )}
        </div>
      )}

      {/* Tab 5: Migration History */}
      {activeTab === "migrations" && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-[#172338] bg-[#090e18] flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-200">Alembic Migration History</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Sequential schema revisions managed under strict forward compatibility.
              </p>
            </div>
            <span className="text-xs font-mono text-emerald-400 px-3 py-1 rounded border border-emerald-800 bg-emerald-950/60">
              {migrations.length} Revisions Recorded
            </span>
          </div>

          <div className="rounded-xl border border-[#172338] bg-[#090e18] divide-y divide-[#172338]">
            {migrations.map((m, idx) => (
              <div key={m.revision} className="p-4 flex items-center justify-between">
                <div className="space-y-1">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono font-bold text-slate-100">{m.revision}</span>
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
                <div className="text-right">
                  <span className="text-xs font-mono text-slate-400">Step {idx + 1}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 6: ER Relationships Diagram */}
      {activeTab === "relationships" && relationships && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-[#172338] bg-[#090e18] flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-200">Entity-Relationship Diagram & Foreign Keys</h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Topological model of application tables and foreign key references.
              </p>
            </div>
            <span className="text-xs font-mono text-slate-300 px-3 py-1 rounded border border-[#172338] bg-[#060911]">
              {relationships.tables.filter((t) => t.category === "application").length} Tables ·{" "}
              {relationships.relationships.length} References
            </span>
          </div>

          {/* ER Diagram Representation */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {relationships.tables
              .filter((t) => t.category === "application")
              .map((table) => {
                const outgoingFks = relationships.relationships.filter(
                  (r) => r.source_table === table.id
                );
                const incomingFks = relationships.relationships.filter(
                  (r) => r.target_table === table.id
                );

                return (
                  <div
                    key={table.id}
                    onClick={() => handleTableSelect(table.id, "structure")}
                    className="p-4 rounded-xl border border-[#172338] bg-[#090e18] hover:border-slate-600 cursor-pointer transition space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono font-bold text-slate-100">{table.id}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                        {table.row_count} rows
                      </span>
                    </div>

                    <div className="space-y-1">
                      <span className="text-[10px] font-mono uppercase text-slate-400">Columns:</span>
                      <div className="flex flex-wrap gap-1">
                        {table.columns.slice(0, 6).map((c) => (
                          <span
                            key={c.name}
                            className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${
                              c.primary_key
                                ? "bg-amber-950 text-amber-300 border-amber-800"
                                : "bg-[#060911] text-slate-400 border-[#172338]"
                            }`}
                          >
                            {c.name}
                          </span>
                        ))}
                        {table.columns.length > 6 && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 text-slate-500">
                            +{table.columns.length - 6} more
                          </span>
                        )}
                      </div>
                    </div>

                    {outgoingFks.length > 0 && (
                      <div className="pt-2 border-t border-[#172338] space-y-1">
                        <span className="text-[10px] font-mono uppercase text-slate-400">References:</span>
                        {outgoingFks.map((fk) => (
                          <p key={fk.id} className="text-[11px] font-mono text-emerald-400">
                            → {fk.target_table} ({fk.source_columns.join(", ")})
                          </p>
                        ))}
                      </div>
                    )}

                    {incomingFks.length > 0 && (
                      <div className="pt-1 space-y-1">
                        <span className="text-[10px] font-mono uppercase text-slate-500">Referenced By:</span>
                        <p className="text-[11px] font-mono text-slate-400">
                          {incomingFks.map((fk) => fk.source_table).join(", ")}
                        </p>
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </div>
  );
}


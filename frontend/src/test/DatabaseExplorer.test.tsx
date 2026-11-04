import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DatabaseExplorerView } from "../features/database-explorer/DatabaseExplorerView";

// Mock API functions
vi.mock("../services/api", async () => {
  const actual = await vi.importActual<Record<string, any>>("../services/api");
  return {
    ...actual,
    fetchDatabaseOverview: vi.fn().mockResolvedValue({
      engine: "sqlite",
      database_name: "app.db",
      file_size_bytes: 10240,
      connection_status: "connected",
      mode: "ro",
      query_only: true,
      integrity_status: "ok",
      current_revision: "0002_task4_media_memory",
      table_counts: {
        total: 24,
        application: 14,
        internal: 0,
        fts5_shadow: 9,
        migration_metadata: 1,
      },
      row_counts: { videos: 1, assets: 1 },
      refreshed_at: "2026-11-02T12:00:00Z",
    }),
    fetchDatabaseTables: vi.fn().mockResolvedValue([
      {
        name: "videos",
        category: "application",
        row_count: 1,
        column_count: 16,
        primary_key: ["id"],
        has_foreign_keys: true,
        foreign_key_count: 2,
        is_empty: false,
      },
    ]),
  };
});

describe("DatabaseExplorerView", () => {
  it("renders the Database Explorer title and authentication controls", () => {
    render(<DatabaseExplorerView />);
    expect(screen.getByText("Live SQLite Database Explorer")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Admin Bearer Token...")).toBeInTheDocument();
    expect(screen.getByText("Authenticate")).toBeInTheDocument();
    expect(screen.getByText("mode=ro · query_only=ON")).toBeInTheDocument();
  });

  it("renders all navigation tabs", () => {
    render(<DatabaseExplorerView />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Tables List")).toBeInTheDocument();
    expect(screen.getByText("Table Structure")).toBeInTheDocument();
    expect(screen.getByText("Paginated Rows")).toBeInTheDocument();
    expect(screen.getByText("Migration History")).toBeInTheDocument();
    expect(screen.getByText("ER Relationships")).toBeInTheDocument();
  });
});


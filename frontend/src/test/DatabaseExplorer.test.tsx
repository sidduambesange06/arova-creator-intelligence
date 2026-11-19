import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DatabaseExplorerView } from "../features/database-explorer/DatabaseExplorerView";

const mockOverview = {
  engine: "sqlite",
  database_name: "app.db",
  file_size_bytes: 798720,
  connection_status: "connected",
  mode: "ro",
  query_only: true,
  integrity_status: "ok",
  current_revision: "0004_transcript_word_timings",
  table_counts: {
    total: 3,
    application: 2,
    internal: 0,
    fts5_shadow: 0,
    migration_metadata: 1,
  },
  row_counts: { videos: 1, transcripts: 1, alembic_version: 1 },
  refreshed_at: "2026-11-20T00:00:00Z",
};

const mockTables = [
  {
    name: "videos",
    category: "application",
    row_count: 1,
    column_count: 3,
    primary_key: ["id"],
    has_foreign_keys: false,
    foreign_key_count: 0,
    is_empty: false,
  },
  {
    name: "transcripts",
    category: "application",
    row_count: 1,
    column_count: 3,
    primary_key: ["id"],
    has_foreign_keys: true,
    foreign_key_count: 1,
    is_empty: false,
  },
];

const mockRows = {
  table_name: "videos",
  category: "application",
  columns: [
    { name: "id", type: "VARCHAR" },
    { name: "filename", type: "VARCHAR" },
    { name: "api_token", type: "VARCHAR" },
    { name: "blob_col", type: "BLOB" },
  ],
  rows: [
    {
      id: "vid-1",
      filename: "ನಮಸ್ಕಾರ_clip.mov",
      api_token: "[REDACTED]",
      blob_col: "<BLOB 64 bytes>",
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
  has_more: false,
};

const mockRelationships = {
  tables: [
    {
      id: "videos",
      label: "videos",
      category: "application",
      row_count: 1,
      column_count: 2,
      columns: [
        { name: "id", type: "VARCHAR", primary_key: true },
        { name: "filename", type: "VARCHAR", primary_key: false },
      ],
    },
    {
      id: "transcripts",
      label: "transcripts",
      category: "application",
      row_count: 1,
      column_count: 2,
      columns: [
        { name: "id", type: "VARCHAR", primary_key: true },
        { name: "video_id", type: "VARCHAR", primary_key: false },
      ],
    },
  ],
  relationships: [
    {
      id: "edge_0",
      source_table: "transcripts",
      source_columns: ["video_id"],
      target_table: "videos",
      target_columns: ["id"],
      label: "video_id -> id",
      relationship_type: "foreign_key",
      is_inferred: false,
    },
  ],
};

describe("DatabaseExplorerView", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows explicit locked guidance before authentication", () => {
    render(<DatabaseExplorerView />);
    expect(screen.getByTestId("db-locked-panel")).toBeInTheDocument();
    expect(screen.getByText(/Database Explorer is Locked/i)).toBeInTheDocument();
    expect(screen.getByText(/ADMIN_AUTH_TOKEN/i)).toBeInTheDocument();
  });

  it("distinguishes unauthorized HTTP 401 clearly", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Invalid or missing admin authentication token." }),
      })
    );

    render(<DatabaseExplorerView />);
    fireEvent.change(screen.getByLabelText(/Local Admin Bearer Token/i), {
      target: { value: "wrong-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Authenticate$/i }));

    await waitFor(() => {
      expect(screen.getByTestId("db-unauthorized-panel")).toBeInTheDocument();
    });
    expect(screen.getByText(/Unauthorized \(HTTP 401\)/i)).toBeInTheDocument();
  });

  it("renders interactive SVG ER diagram, avoids redundant overview calls, and clears state on Lock", async () => {
    const calledUrls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (input: string) => {
        calledUrls.push(String(input));
        if (input.endsWith("/overview")) {
          return { ok: true, status: 200, json: async () => mockOverview };
        }
        if (input.includes("/tables/videos/rows")) {
          return { ok: true, status: 200, json: async () => mockRows };
        }
        if (input.includes("/tables")) {
          return { ok: true, status: 200, json: async () => mockTables };
        }
        if (input.endsWith("/relationships")) {
          return { ok: true, status: 200, json: async () => mockRelationships };
        }
        return { ok: true, status: 200, json: async () => [] };
      })
    );

    render(<DatabaseExplorerView />);
    fireEvent.change(screen.getByLabelText(/Local Admin Bearer Token/i), {
      target: { value: "valid-local-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Authenticate$/i }));

    await waitFor(() => {
      expect(screen.getByText("0004_transcript_word_timings")).toBeInTheDocument();
    });
    const overviewCountAfterAuth = calledUrls.filter((u) => u.endsWith("/overview")).length;
    expect(overviewCountAfterAuth).toBe(1);

    // Click 'videos' table -> opens Paginated Rows WITHOUT re-calling /overview
    fireEvent.click(screen.getByRole("button", { name: /videos/i }));
    await waitFor(() => {
      expect(screen.getByText("ನಮಸ್ಕಾರ_clip.mov")).toBeInTheDocument();
      expect(screen.getByText("[REDACTED]")).toBeInTheDocument();
      expect(screen.getByText("<BLOB 64 bytes>")).toBeInTheDocument();
    });
    expect(calledUrls.filter((u) => u.endsWith("/overview")).length).toBe(1);

    // Switch to ER Relationships -> verify SVG diagram, zoom, node selection & accessible list view
    fireEvent.click(screen.getByRole("tab", { name: /ER Relationships/i }));
    await waitFor(() => {
      expect(screen.getByTestId("er-diagram-canvas")).toBeInTheDocument();
      expect(screen.getByRole("img", { name: /Entity-Relationship Schema Diagram/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/0 inferred/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Zoom in/i }));
    expect(screen.getByText("115%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Table transcripts/i }));
    expect(screen.getByText(/Outgoing Foreign Keys \(1\)/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Accessible List View/i }));
    expect(screen.getByRole("columnheader", { name: /Actual SQLite Foreign Keys/i })).toBeInTheDocument();

    // Lock clears token & returns to locked panel
    fireEvent.click(screen.getByRole("button", { name: /^Lock$/i }));
    expect(screen.getByTestId("db-locked-panel")).toBeInTheDocument();
    expect(sessionStorage.getItem("arova_admin_token")).toBeNull();
  });
});

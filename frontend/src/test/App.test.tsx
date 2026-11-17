import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

describe("App Inspector Shell", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders live health status from GET /api/v1/health", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/health")) {
        return new Response(
          JSON.stringify({
            status: "ok",
            service: "Arova Creator Intelligence",
            version: "0.1.0",
            environment: "development",
            timestamp: "2026-10-30T13:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }
      return new Response("{}", { status: 200 });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("health-badge")).toHaveTextContent("online");
    });
    expect(screen.getByText("v0.1.0 (development)")).toBeInTheDocument();
  });

  it("surfaces error state when backend health endpoint is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/api/v1/health")) {
        throw new Error("Connection refused");
      }
      return new Response("{}", { status: 200 });
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId("health-badge")).toHaveTextContent("offline");
    });
    expect(screen.getAllByText(/Connection refused/i).length).toBeGreaterThan(0);
  });
});

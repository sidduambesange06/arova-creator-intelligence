import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { ErrorBoundary } from "../components/ErrorBoundary";

function DynamicHarness() {
  const [hasCrash, setHasCrash] = useState(true);

  if (hasCrash) {
    return (
      <div>
        <button onClick={() => setHasCrash(false)}>Fix Error</button>
        {(() => {
          throw new Error("Simulated component crash");
        })()}
      </div>
    );
  }

  return <div>Component rendered safely</div>;
}

describe("ErrorBoundary", () => {
  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <div>Component rendered safely</div>
      </ErrorBoundary>
    );
    expect(screen.getByText("Component rendered safely")).toBeInTheDocument();
  });

  it("catches error, displays diagnostic details, and supports recovery", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <DynamicHarness />
      </ErrorBoundary>
    );

    expect(screen.getByText("Application Component Recovered")).toBeInTheDocument();
    expect(screen.getByText(/Simulated component crash/)).toBeInTheDocument();
    expect(screen.getByText("Reload View")).toBeInTheDocument();
    expect(screen.getByText("Reset to Cockpit")).toBeInTheDocument();

    // Verify recovery button can be clicked without throwing
    fireEvent.click(screen.getByText("Reload View"));

    spy.mockRestore();
  });
});

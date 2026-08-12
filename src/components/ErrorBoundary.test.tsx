import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { screen } from "@testing-library/react";
import ErrorBoundary from "./ErrorBoundary";
import { renderWithProviders } from "../test/utils";

function Boom({ message }: { message: string }): never {
  throw new Error(message);
}

const CHUNK_FAILURE = "Failed to fetch dynamically imported module: /assets/GroupPage-abc.js";

let reload: ReturnType<typeof vi.fn>;

beforeEach(() => {
  sessionStorage.clear();
  reload = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, reload },
  });
  // React logs the caught error; keep the test output readable.
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => vi.restoreAllMocks());

describe("ErrorBoundary", () => {
  it("reloads once when a lazy chunk fails to load", () => {
    // The real case: a client on an old app shell navigates after a deploy
    // has replaced the chunk hashes. Suspense covers a pending import, never
    // a rejected one, so without this the tree unmounts to a blank page.
    renderWithProviders(
      <ErrorBoundary>
        <Boom message={CHUNK_FAILURE} />
      </ErrorBoundary>,
    );

    expect(reload).toHaveBeenCalledOnce();
  });

  it("stops reloading if the chunk is still missing after a refresh", () => {
    renderWithProviders(
      <ErrorBoundary>
        <Boom message={CHUNK_FAILURE} />
      </ErrorBoundary>,
    );
    expect(reload).toHaveBeenCalledOnce();

    // Second failure inside the cooldown: a genuinely missing chunk must not
    // become an infinite refresh loop, which is worse than a blank screen.
    renderWithProviders(
      <ErrorBoundary>
        <Boom message={CHUNK_FAILURE} />
      </ErrorBoundary>,
    );
    expect(reload).toHaveBeenCalledOnce();
    expect(screen.getAllByText("Something went wrong").length).toBeGreaterThan(0);
  });

  it("does not reload on an ordinary render error", () => {
    // Reloading a crash that isn't a stale chunk just repeats the crash.
    renderWithProviders(
      <ErrorBoundary>
        <Boom message="Cannot read properties of undefined" />
      </ErrorBoundary>,
    );

    expect(reload).not.toHaveBeenCalled();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload" })).toBeInTheDocument();
  });
});

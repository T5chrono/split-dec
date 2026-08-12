import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import { renderWithProviders } from "./test/utils";

vi.mock("./hooks/useAuth", () => ({
  useAuth: () => ({
    session: null,
    loading: false,
    passwordRecovery: false,
    signInWithGoogle: vi.fn(),
    signInWithPassword: vi.fn(),
    signUpWithPassword: vi.fn(),
    requestPasswordReset: vi.fn(),
    signOut: vi.fn(),
  }),
}));

function renderAt(path: string) {
  return renderWithProviders(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("App routing", () => {
  it("resolves a lazy route through Suspense", async () => {
    // Guards the split itself: without the <Suspense> boundary React throws
    // when a lazy element suspends, and every route below is code-split.
    renderAt("/privacy");
    expect(
      await screen.findByRole("heading", { level: 1, name: "Privacy Policy" }),
    ).toBeInTheDocument();
  });

  it("renders the lazily-loaded landing page at the signed-out root", async () => {
    renderAt("/");
    expect(
      await screen.findByRole("heading", { level: 1, name: /split expenses/i }),
    ).toBeInTheDocument();
  });

  it("keeps signed-out deep links on the sign-in screen", async () => {
    // Load-bearing: an invitation email link lands signed-out, and the
    // focused sign-in screen is what carries the visitor to the original URL
    // after authenticating. A 404 or a bounce to "/" would break invites.
    renderAt("/groups/some-group-id");
    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByText("Page not found")).not.toBeInTheDocument();
  });
});

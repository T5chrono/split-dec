import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import App from "../App";
import NotFoundPage from "./NotFoundPage";
import { renderWithProviders } from "../test/utils";

vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    session: { user: { id: "u1", email: "a@test.dev", user_metadata: {} } },
    loading: false,
    passwordRecovery: false,
    signOut: vi.fn(),
    signInWithGoogle: vi.fn(),
  }),
}));

vi.mock("../lib/api", () => ({
  api: { get: vi.fn().mockResolvedValue([]), post: vi.fn(), delete: vi.fn(), patch: vi.fn() },
  ApiError: class extends Error {},
  newIdempotencyKey: () => "key",
}));

describe("NotFoundPage", () => {
  it("renders the message and a way back", () => {
    renderWithProviders(
      <MemoryRouter>
        <Routes>
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { level: 1, name: "Page not found" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to your groups" })).toHaveAttribute(
      "href",
      "/",
    );
  });

  it("an unmatched signed-in route shows the 404 instead of silently redirecting", async () => {
    renderWithProviders(
      <MemoryRouter initialEntries={["/this/does/not/exist"]}>
        <App />
      </MemoryRouter>,
    );

    // The old behaviour was <Navigate to="/">, which made a stale link look
    // like it had worked by landing the user on the groups list.
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
    expect(screen.queryByText("Your groups")).not.toBeInTheDocument();
  });
});

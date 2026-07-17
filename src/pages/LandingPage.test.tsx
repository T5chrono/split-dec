import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LandingPage from "./LandingPage";
import { renderWithProviders } from "../test/utils";

const signInWithGoogle = vi.fn();
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    session: null,
    loading: false,
    signInWithGoogle,
    signOut: vi.fn(),
  }),
}));

beforeEach(() => {
  signInWithGoogle.mockClear();
  localStorage.clear();
});

describe("LandingPage", () => {
  it("renders the hero, features and steps", () => {
    renderWithProviders(<LandingPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /split expenses/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Groups for everything")).toBeInTheDocument();
    expect(screen.getByText("Settled up in three steps")).toBeInTheDocument();
  });

  it("starts Google sign-in from every CTA", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LandingPage />);

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    for (const cta of screen.getAllByRole("button", { name: /continue with google/i })) {
      await user.click(cta);
    }
    expect(signInWithGoogle).toHaveBeenCalledTimes(3);
  });

  it("switches the whole page to Polish", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LandingPage />);

    await user.click(screen.getByRole("button", { name: /pl/i }));
    expect(
      screen.getByRole("heading", { level: 1, name: /dziel wydatki/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
  });
});

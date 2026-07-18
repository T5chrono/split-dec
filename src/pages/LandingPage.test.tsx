import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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

function renderPage() {
  return renderWithProviders(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<div>login screen</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  signInWithGoogle.mockClear();
  localStorage.clear();
});

describe("LandingPage", () => {
  it("renders the hero, features and steps", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { level: 1, name: /split expenses/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Groups for everything")).toBeInTheDocument();
    expect(screen.getByText("Settled up in three steps")).toBeInTheDocument();
  });

  it("starts Google sign-in from the hero and bottom CTAs", async () => {
    const user = userEvent.setup();
    renderPage();

    for (const cta of screen.getAllByRole("button", { name: /continue with google/i })) {
      await user.click(cta);
    }
    expect(signInWithGoogle).toHaveBeenCalledTimes(2);
  });

  it("routes the header sign-in and the email link to the login page", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByText("login screen")).toBeInTheDocument();
    expect(signInWithGoogle).not.toHaveBeenCalled();
  });

  it("offers email sign-in under the hero CTA", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign in with email" }));
    expect(screen.getByText("login screen")).toBeInTheDocument();
    expect(signInWithGoogle).not.toHaveBeenCalled();
  });

  it("switches the whole page to Polish", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /pl/i }));
    expect(
      screen.getByRole("heading", { level: 1, name: /dziel wydatki/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
  });
});

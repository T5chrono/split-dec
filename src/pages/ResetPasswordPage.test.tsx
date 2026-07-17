import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthError } from "@supabase/supabase-js";
import type { Session } from "@supabase/supabase-js";
import ResetPasswordPage from "./ResetPasswordPage";
import { renderWithProviders } from "../test/utils";

const updatePassword = vi.fn();
const signOut = vi.fn();
let session: Session | null;
let loading: boolean;
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    session,
    loading,
    passwordRecovery: true,
    signInWithGoogle: vi.fn(),
    signOut,
    signInWithPassword: vi.fn(),
    signUpWithPassword: vi.fn(),
    requestPasswordReset: vi.fn(),
    updatePassword,
  }),
}));

function renderPage() {
  return renderWithProviders(
    <MemoryRouter initialEntries={["/reset-password"]}>
      <ResetPasswordPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  updatePassword.mockResolvedValue(undefined);
  session = { user: { id: "user-a" } } as Session;
  loading = false;
  localStorage.clear();
});

describe("ResetPasswordPage", () => {
  it("shows the invalid-link state without a session", () => {
    session = null;
    renderPage();
    expect(screen.getByText(/invalid or has expired/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to sign in" })).toBeInTheDocument();
  });

  it("rejects mismatched passwords without calling supabase", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("New password"), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "password124");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/don't match/i);
    expect(updatePassword).not.toHaveBeenCalled();
  });

  it("updates the password and confirms success", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("New password"), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "password123");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(updatePassword).toHaveBeenCalledWith("password123");
    expect(await screen.findByRole("status")).toHaveTextContent(/password updated/i);
  });

  it("shows a mapped error when the new password is rejected", async () => {
    const user = userEvent.setup();
    updatePassword.mockRejectedValueOnce(
      Object.assign(new AuthError("weak"), { status: 422, code: "same_password" }),
    );
    renderPage();

    await user.type(screen.getByLabelText("New password"), "password123");
    await user.type(screen.getByLabelText("Confirm password"), "password123");
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/must be different/i);
  });

  it("offers a sign-out escape for unwanted recovery sessions", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Not you? Sign out" }));
    expect(signOut).toHaveBeenCalled();
  });
});

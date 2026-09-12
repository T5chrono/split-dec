import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthError } from "@supabase/supabase-js";
import type { Session } from "@supabase/supabase-js";
import ResetPasswordPage from "./ResetPasswordPage";
import { MIN_PASSWORD_LENGTH } from "../lib/authErrors";
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

// Exactly the minimum, and a second one that differs only in its last
// character — the mismatch test needs two valid-length passwords.
const PASSWORD = "password1234";
const PASSWORD_TYPO = "password1235";

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

    await user.type(screen.getByLabelText("New password"), PASSWORD);
    await user.type(screen.getByLabelText("Confirm password"), PASSWORD_TYPO);
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/don't match/i);
    expect(updatePassword).not.toHaveBeenCalled();
  });

  it("refuses a password below the minimum without calling supabase", async () => {
    const user = userEvent.setup();
    const oneShort = PASSWORD.slice(0, MIN_PASSWORD_LENGTH - 1);
    renderPage();

    await user.type(screen.getByLabelText("New password"), oneShort);
    await user.type(screen.getByLabelText("Confirm password"), oneShort);
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      `at least ${MIN_PASSWORD_LENGTH} characters`,
    );
    expect(updatePassword).not.toHaveBeenCalled();
  });

  it("states the length rule on the field that has to meet it", () => {
    renderPage();
    const hint = screen.getByText(`At least ${MIN_PASSWORD_LENGTH} characters`, {
      exact: false,
    });
    expect(screen.getByLabelText("New password")).toHaveAttribute(
      "aria-describedby",
      hint.id,
    );
  });

  it("updates the password and confirms success", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("New password"), PASSWORD);
    await user.type(screen.getByLabelText("Confirm password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Set new password" }));

    expect(updatePassword).toHaveBeenCalledWith(PASSWORD);
    expect(await screen.findByRole("status")).toHaveTextContent(/password updated/i);
  });

  it("shows a mapped error when the new password is rejected", async () => {
    const user = userEvent.setup();
    updatePassword.mockRejectedValueOnce(
      Object.assign(new AuthError("weak"), { status: 422, code: "same_password" }),
    );
    renderPage();

    await user.type(screen.getByLabelText("New password"), PASSWORD);
    await user.type(screen.getByLabelText("Confirm password"), PASSWORD);
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

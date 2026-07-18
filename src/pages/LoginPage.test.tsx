import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthError } from "@supabase/supabase-js";
import LoginPage from "./LoginPage";
import { renderWithProviders } from "../test/utils";

const signInWithGoogle = vi.fn();
const signInWithPassword = vi.fn();
const signUpWithPassword = vi.fn();
const requestPasswordReset = vi.fn();
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    session: null,
    loading: false,
    passwordRecovery: false,
    signInWithGoogle,
    signOut: vi.fn(),
    signInWithPassword,
    signUpWithPassword,
    requestPasswordReset,
    updatePassword: vi.fn(),
  }),
}));

const authError = (code: string) =>
  Object.assign(new AuthError("nope"), { status: 400, code });

function renderPage() {
  return renderWithProviders(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  signUpWithPassword.mockResolvedValue({ needsConfirmation: true });
  signInWithPassword.mockResolvedValue(undefined);
  requestPasswordReset.mockResolvedValue(undefined);
  localStorage.clear();
  window.history.replaceState(null, "", "/");
});

describe("LoginPage", () => {
  it("shows the sign-in form with Google and email options", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("toggles between sign-in, sign-up and forgot-password modes", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    expect(screen.getByLabelText("Full name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    await user.click(screen.getByRole("button", { name: "Forgot password?" }));
    expect(screen.getByRole("button", { name: "Send reset link" })).toBeInTheDocument();
  });

  it("signs in with email and password", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText("Email"), "ala@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(signInWithPassword).toHaveBeenCalledWith("ala@example.com", "password123");
  });

  it("shows a mapped error for invalid credentials", async () => {
    const user = userEvent.setup();
    signInWithPassword.mockRejectedValueOnce(authError("invalid_credentials"));
    renderPage();

    await user.type(screen.getByLabelText("Email"), "ala@example.com");
    await user.type(screen.getByLabelText("Password"), "wrongpass1");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Incorrect email or password.",
    );
  });

  it("rejects a too-short password on sign-up without calling supabase", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    await user.type(screen.getByLabelText("Full name"), "Ala Kot");
    await user.type(screen.getByLabelText("Email"), "ala@example.com");
    await user.type(screen.getByLabelText("Password"), "short12");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/at least 8 characters/);
    expect(signUpWithPassword).not.toHaveBeenCalled();
  });

  it("shows the check-your-email screen after signing up", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    await user.type(screen.getByLabelText("Full name"), "Ala Kot");
    await user.type(screen.getByLabelText("Email"), "ala@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(signUpWithPassword).toHaveBeenCalledWith("ala@example.com", "password123", "Ala Kot");
    expect(await screen.findByText("Check your email")).toBeInTheDocument();
    expect(screen.getByText(/ala@example\.com/)).toBeInTheDocument();
  });

  it("shows a neutral confirmation after requesting a reset link", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Forgot password?" }));
    await user.type(screen.getByLabelText("Email"), "ala@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(requestPasswordReset).toHaveBeenCalledWith("ala@example.com");
    expect(await screen.findByText(/if an account exists/i)).toBeInTheDocument();
  });

  it("surfaces an expired-link error code from the URL", () => {
    window.history.replaceState(null, "", "/?error_code=otp_expired");
    renderPage();
    expect(screen.getByRole("alert")).toHaveTextContent(/link has expired/i);
  });

  it("renders in Polish", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /pl/i }));
    expect(screen.getByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
    expect(screen.getByLabelText("Hasło")).toBeInTheDocument();
  });
});

import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AuthError } from "@supabase/supabase-js";
import LoginPage from "./LoginPage";
import { MAX_FULL_NAME_LENGTH, MIN_PASSWORD_LENGTH } from "../lib/authErrors";
import { SUPPORT_URL } from "../lib/support";
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

// Exactly the minimum, so the boundary is exercised as *accepted* on every
// happy path, and one below it in the test that expects a refusal.
const PASSWORD = "password1234";
const ONE_SHORT = "password123";

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
  it("never asks for money here", () => {
    // This screen is where an invitation deep link lands a signed-out
    // visitor. Asking someone to buy a coffee before they can even join the
    // group they were invited to is the wrong first impression, so the
    // support link stays off it — unlike the legal links beside it.
    renderPage();

    const links = screen.queryAllByRole("link");
    expect(links.some((a) => a.getAttribute("href") === SUPPORT_URL)).toBe(false);
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toBeInTheDocument();
  });

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
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(signInWithPassword).toHaveBeenCalledWith("ala@example.com", PASSWORD);
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
    // One character short, pinned to the constant so the fixture cannot drift
    // away from the boundary it is here to test.
    expect(ONE_SHORT).toHaveLength(MIN_PASSWORD_LENGTH - 1);
    await user.type(screen.getByLabelText("Password"), ONE_SHORT);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      `at least ${MIN_PASSWORD_LENGTH} characters`,
    );
    expect(signUpWithPassword).not.toHaveBeenCalled();
  });

  it("states the length rule before anyone runs into it", () => {
    renderPage();
    // Sign-in has no hint — the rule only applies to a password being set.
    expect(screen.queryByText(/at least 12 characters/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));
    const hint = screen.getByText(`At least ${MIN_PASSWORD_LENGTH} characters`, {
      exact: false,
    });
    expect(hint).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "aria-describedby",
      hint.id,
    );
  });

  it("shows the check-your-email screen after signing up", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    await user.type(screen.getByLabelText("Full name"), "Ala Kot");
    await user.type(screen.getByLabelText("Email"), "ala@example.com");
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(signUpWithPassword).toHaveBeenCalledWith("ala@example.com", PASSWORD, "Ala Kot");
    expect(await screen.findByText("Check your email")).toBeInTheDocument();
    expect(screen.getByText(/ala@example\.com/)).toBeInTheDocument();
  });

  it("tells an address that already has an account exactly what it tells a new one", async () => {
    // The enumeration guard. With Supabase's "Confirm email" on, a duplicate
    // signup comes back as a session-less success and never reaches this
    // path — but that is a dashboard toggle, and this page must not be the
    // thing that starts answering "does this person have an account here?"
    // the day somebody turns it off.
    const user = userEvent.setup();
    signUpWithPassword.mockRejectedValueOnce(authError("user_already_exists"));
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    await user.type(screen.getByLabelText("Full name"), "Ala Kot");
    await user.type(screen.getByLabelText("Email"), "taken@example.com");
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Check your email")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("caps the name it sends, even when the input is filled around maxLength", async () => {
    // A courtesy cap, not a security boundary — `full_name` reaches the
    // database through Supabase Auth's signup metadata, not through our API,
    // so a direct Auth call bypasses this. The slice is here because
    // `maxLength` does not bind a programmatic value change.
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Sign up" }));
    const name = screen.getByLabelText("Full name") as HTMLInputElement;
    expect(name.maxLength).toBe(MAX_FULL_NAME_LENGTH);

    fireEvent.change(name, { target: { value: "A".repeat(MAX_FULL_NAME_LENGTH + 50) } });
    await user.type(screen.getByLabelText("Email"), "ala@example.com");
    await user.type(screen.getByLabelText("Password"), PASSWORD);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(signUpWithPassword).toHaveBeenCalledWith(
      "ala@example.com",
      PASSWORD,
      "A".repeat(MAX_FULL_NAME_LENGTH),
    );
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

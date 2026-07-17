import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useI18n, type TKey } from "../lib/i18n";
import { TileMark, Wordmark } from "../components/Logo";
import GoogleIcon from "../components/GoogleIcon";
import { MIN_PASSWORD_LENGTH, mapAuthError } from "../lib/authErrors";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800";
const labelCls = "mb-1 block text-sm font-medium";
const submitCls =
  "w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50";
const linkBtnCls =
  "font-medium text-teal-700 hover:underline dark:text-teal-300";

type Mode = "signin" | "signup" | "forgot" | "checkEmailSignup" | "checkEmailReset";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Supabase appends error_code (e.g. otp_expired) to the redirect target when
// a verify link is invalid — in the query string or the hash fragment.
function urlErrorBanner(): TKey | null {
  const search = new URLSearchParams(window.location.search);
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const code = search.get("error_code") ?? hash.get("error_code");
  if (!code) return null;
  return code === "otp_expired" ? "errOtpExpired" : "errAuthGeneric";
}

export default function LoginPage() {
  const { signInWithGoogle, signInWithPassword, signUpWithPassword, requestPasswordReset } =
    useAuth();
  const { t, lang, setLang } = useI18n();

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<TKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [linkError] = useState<TKey | null>(urlErrorBanner);

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
  };

  const submitSignIn = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      // No redirect: onAuthStateChange delivers SIGNED_IN and App re-renders
      // into the signed-in branch with the current URL (deep links survive).
      await signInWithPassword(email.trim(), password);
    } catch (err) {
      setError(mapAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const submitSignUp = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedEmail = email.trim();
    if (!EMAIL_RE.test(trimmedEmail)) return setError("errInvalidEmail");
    if (password.length < MIN_PASSWORD_LENGTH) return setError("errWeakPassword");
    setError(null);
    setBusy(true);
    try {
      await signUpWithPassword(trimmedEmail, password, fullName.trim());
      setMode("checkEmailSignup");
    } catch (err) {
      setError(mapAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const submitForgot = async (e: FormEvent) => {
    e.preventDefault();
    const trimmedEmail = email.trim();
    if (!EMAIL_RE.test(trimmedEmail)) return setError("errInvalidEmail");
    setError(null);
    setBusy(true);
    try {
      await requestPasswordReset(trimmedEmail);
      setMode("checkEmailReset");
    } catch (err) {
      setError(mapAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const errorAlert = error && (
    <p role="alert" className="text-sm text-red-600 dark:text-red-400">
      {t(error)}
    </p>
  );

  const checkEmail = mode === "checkEmailSignup" || mode === "checkEmailReset";

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4 py-10">
      <button
        onClick={() => setLang(lang === "en" ? "pl" : "en")}
        className="absolute right-4 top-4 rounded-md px-3 py-1.5 text-xs font-semibold uppercase text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
      >
        {lang === "en" ? "PL" : "EN"}
      </button>
      <div className="flex flex-col items-center gap-2">
        <Link to="/" className="flex flex-col items-center gap-2">
          <TileMark className="h-16 w-16" />
          <h1 className="text-3xl">
            <Wordmark />
          </h1>
        </Link>
        <p className="text-slate-500 dark:text-slate-400">{t("tagline")}</p>
      </div>

      <div className="flex w-full max-w-sm flex-col gap-5">
        {linkError && !checkEmail && (
          <p
            role="alert"
            className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200"
          >
            {t(linkError)}
          </p>
        )}

        {checkEmail ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <h2 className="text-lg font-semibold">{t("checkEmailTitle")}</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300">
              {t(
                mode === "checkEmailSignup" ? "checkEmailSignupBody" : "checkEmailResetBody",
              ).replace("{email}", email.trim())}
            </p>
            <button onClick={() => switchMode("signin")} className={linkBtnCls}>
              {t("backToSignIn")}
            </button>
          </div>
        ) : (
          <>
            <button
              onClick={signInWithGoogle}
              className="flex items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white px-6 py-3 font-medium shadow-sm hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-900 dark:hover:bg-slate-800"
            >
              <GoogleIcon />
              {t("continueWithGoogle")}
            </button>

            <div
              className="flex items-center gap-3 text-sm text-slate-400 dark:text-slate-500"
              aria-hidden="true"
            >
              <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
              {t("orDivider")}
              <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
            </div>

            {mode === "signin" && (
              <form onSubmit={submitSignIn} className="flex flex-col gap-3">
                <div>
                  <label htmlFor="login-email" className={labelCls}>
                    {t("email")}
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label htmlFor="login-password" className={labelCls}>
                    {t("password")}
                  </label>
                  <input
                    id="login-password"
                    type="password"
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputCls}
                  />
                </div>
                {errorAlert}
                <button type="submit" disabled={busy} className={submitCls}>
                  {busy ? t("signingIn") : t("signIn")}
                </button>
                <div className="flex flex-col items-center gap-1 text-sm text-slate-600 dark:text-slate-300">
                  <button type="button" onClick={() => switchMode("forgot")} className={linkBtnCls}>
                    {t("forgotPassword")}
                  </button>
                  <p>
                    {t("noAccountYet")}{" "}
                    <button
                      type="button"
                      onClick={() => switchMode("signup")}
                      className={linkBtnCls}
                    >
                      {t("signUp")}
                    </button>
                  </p>
                </div>
              </form>
            )}

            {mode === "signup" && (
              <form onSubmit={submitSignUp} className="flex flex-col gap-3">
                <div>
                  <label htmlFor="signup-name" className={labelCls}>
                    {t("fullName")}
                  </label>
                  <input
                    id="signup-name"
                    type="text"
                    required
                    autoComplete="name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label htmlFor="signup-email" className={labelCls}>
                    {t("email")}
                  </label>
                  <input
                    id="signup-email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label htmlFor="signup-password" className={labelCls}>
                    {t("password")}
                  </label>
                  <input
                    id="signup-password"
                    type="password"
                    required
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputCls}
                  />
                </div>
                {errorAlert}
                <button type="submit" disabled={busy} className={submitCls}>
                  {busy ? t("creating") : t("createAccount")}
                </button>
                <p className="text-center text-sm text-slate-600 dark:text-slate-300">
                  {t("alreadyHaveAccount")}{" "}
                  <button type="button" onClick={() => switchMode("signin")} className={linkBtnCls}>
                    {t("signIn")}
                  </button>
                </p>
              </form>
            )}

            {mode === "forgot" && (
              <form onSubmit={submitForgot} className="flex flex-col gap-3">
                <div>
                  <label htmlFor="forgot-email" className={labelCls}>
                    {t("email")}
                  </label>
                  <input
                    id="forgot-email"
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={inputCls}
                  />
                </div>
                {errorAlert}
                <button type="submit" disabled={busy} className={submitCls}>
                  {busy ? t("sendingResetLink") : t("sendResetLink")}
                </button>
                <button
                  type="button"
                  onClick={() => switchMode("signin")}
                  className={`text-sm ${linkBtnCls}`}
                >
                  {t("backToSignIn")}
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </div>
  );
}

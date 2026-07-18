import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useI18n, type TKey } from "../lib/i18n";
import { TileMark, Wordmark } from "../components/Logo";
import Spinner from "../components/Spinner";
import { MIN_PASSWORD_LENGTH, mapAuthError } from "../lib/authErrors";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800";
const labelCls = "mb-1 block text-sm font-medium";
const submitCls =
  "w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50";
const linkBtnCls = "text-sm font-medium text-teal-700 hover:underline dark:text-teal-300";

/** Landing screen for Supabase password-recovery links (and, when visited
 *  signed-in, a plain change-password screen). Registered in both auth
 *  branches of App: the link arrives signed-out, the SDK exchanges the code
 *  and the app re-renders signed-in on the same path. */
export default function ResetPasswordPage() {
  const { session, loading, signOut, updatePassword } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<TKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!done) return;
    const id = setTimeout(() => navigate("/", { replace: true }), 1500);
    return () => clearTimeout(id);
  }, [done, navigate]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (password.length < MIN_PASSWORD_LENGTH) return setError("errWeakPassword");
    if (password !== confirm) return setError("errPasswordMismatch");
    setError(null);
    setBusy(true);
    try {
      await updatePassword(password);
      setDone(true);
    } catch (err) {
      setError(mapAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4 py-10">
      <div className="flex flex-col items-center gap-2">
        <Link to="/" className="flex flex-col items-center gap-2">
          <TileMark className="h-16 w-16" />
          <h1 className="text-3xl">
            <Wordmark />
          </h1>
        </Link>
      </div>

      <div className="flex w-full max-w-sm flex-col gap-5">
        {!session ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <p className="text-sm text-slate-600 dark:text-slate-300">{t("resetLinkInvalid")}</p>
            <Link to="/login" className={linkBtnCls}>
              {t("backToSignIn")}
            </Link>
          </div>
        ) : done ? (
          <p role="status" className="text-center text-sm text-slate-600 dark:text-slate-300">
            {t("passwordUpdated")}
          </p>
        ) : (
          <form onSubmit={submit} className="flex flex-col gap-3">
            <h2 className="text-center text-lg font-semibold">{t("resetPasswordTitle")}</h2>
            <div>
              <label htmlFor="new-password" className={labelCls}>
                {t("newPassword")}
              </label>
              <input
                id="new-password"
                type="password"
                required
                autoComplete="new-password"
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputCls}
              />
            </div>
            <div>
              <label htmlFor="confirm-password" className={labelCls}>
                {t("confirmPassword")}
              </label>
              <input
                id="confirm-password"
                type="password"
                required
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className={inputCls}
              />
            </div>
            {error && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {t(error)}
              </p>
            )}
            <button type="submit" disabled={busy} className={submitCls}>
              {busy ? t("updatingPassword") : t("setNewPassword")}
            </button>
            <button type="button" onClick={signOut} className={linkBtnCls}>
              {t("signOutRecovery")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

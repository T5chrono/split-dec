import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../lib/i18n";
import { TileMark, Wordmark } from "../components/Logo";
import GoogleIcon from "../components/GoogleIcon";

export default function LoginPage() {
  const { signInWithGoogle } = useAuth();
  const { t, lang, setLang } = useI18n();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-4">
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
      <button
        onClick={signInWithGoogle}
        className="flex items-center gap-3 rounded-lg border border-slate-300 bg-white px-6 py-3 font-medium shadow-sm hover:bg-slate-50 dark:border-slate-600 dark:bg-slate-900 dark:hover:bg-slate-800"
      >
        <GoogleIcon />
        {t("continueWithGoogle")}
      </button>
    </div>
  );
}

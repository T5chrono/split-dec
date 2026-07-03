import { useState } from "react";
import { Link, Outlet } from "react-router-dom";
import { Languages, Moon, Split, Sun, UserRound } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTheme } from "../hooks/useTheme";
import { useI18n } from "../lib/i18n";
import AccountModal from "./AccountModal";

export default function Layout() {
  const { session } = useAuth();
  const { theme, toggle } = useTheme();
  const { lang, setLang, t } = useI18n();
  const [accountOpen, setAccountOpen] = useState(false);

  const meta = session?.user.user_metadata as
    | { avatar_url?: string; picture?: string }
    | undefined;
  const avatar = meta?.avatar_url ?? meta?.picture;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link
            to="/"
            className="flex items-center gap-2 text-lg font-bold text-teal-700 dark:text-teal-400"
          >
            <Split className="h-5 w-5" />
            SplitDec
          </Link>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setLang(lang === "en" ? "pl" : "en")}
              title={t("language")}
              className="flex items-center gap-1 rounded-md px-2 py-2 text-xs font-semibold uppercase text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              <Languages className="h-4 w-4" />
              {lang === "en" ? "PL" : "EN"}
            </button>
            <button
              onClick={toggle}
              title={theme === "dark" ? t("lightMode") : t("darkMode")}
              className="rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <button
              onClick={() => setAccountOpen(true)}
              title={t("account")}
              className="ml-1 rounded-full ring-teal-500 hover:ring-2"
            >
              {avatar ? (
                <img
                  src={avatar}
                  alt={t("account")}
                  className="h-8 w-8 rounded-full"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-teal-100 text-teal-700 dark:bg-teal-900 dark:text-teal-300">
                  <UserRound className="h-4 w-4" />
                </span>
              )}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <Outlet />
      </main>
      {accountOpen && <AccountModal onClose={() => setAccountOpen(false)} />}
    </div>
  );
}

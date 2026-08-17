import { Fragment, useEffect, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Languages, Moon, Sun } from "lucide-react";
import { useTheme } from "../hooks/useTheme";
import { useI18n } from "../lib/i18n";
import { formatDateOnly } from "../lib/dates";
import { LEGAL_DOCS, LEGAL_UPDATED, type LegalDocId } from "../lib/legal";
import { CoinMark, Wordmark } from "../components/Logo";

/** Inline markup understood inside a legal block: `**bold**` and
 *  `[label](href)`. Deliberately not a markdown parser — the documents are
 *  ours, so supporting exactly the two things they use keeps this small and
 *  removes any question of rendering untrusted input. */
const INLINE_RE = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)/g;

/** Schemes a legal-document link is allowed to use.
 *
 *  `javascript:` is the whole reason this exists. React warns about such URLs
 *  but does not block them, so `[click](javascript:…)` in a document body would
 *  be a working XSS — harmless today, because the only input is the static copy
 *  in `lib/legal.ts`, and a real hole the moment that copy comes from anywhere
 *  else. Adding the check now costs nothing and means the future change that
 *  makes these documents dynamic cannot quietly introduce one.
 *
 *  Both documents together use exactly three link shapes — `/privacy`,
 *  `https://…` and one `mailto:` — so nothing needs rewriting to satisfy this.
 *  A link with any other scheme renders as plain label text rather than
 *  disappearing, because silently dropping words from a legal document is worse
 *  than showing them unlinked.
 */
const SAFE_HREF = /^(?:https:|mailto:)/i;

export function renderLegalText(text: string): ReactNode {
  const out: ReactNode[] = [];
  let last = 0;

  for (const m of text.matchAll(INLINE_RE)) {
    const start = m.index;
    if (start > last) out.push(text.slice(last, start));

    const [, bold, label, href] = m;
    if (bold !== undefined) {
      out.push(<strong key={start}>{bold}</strong>);
    } else if (href!.startsWith("/")) {
      // In-app route: keep it a client-side navigation.
      out.push(
        <Link key={start} to={href!} className="text-teal-700 underline dark:text-teal-300">
          {label}
        </Link>,
      );
    } else if (SAFE_HREF.test(href!)) {
      const external = href!.toLowerCase().startsWith("https:");
      out.push(
        <a
          key={start}
          href={href!}
          {...(external ? { target: "_blank", rel: "noreferrer" } : {})}
          className="text-teal-700 underline dark:text-teal-300"
        >
          {label}
        </a>,
      );
    } else {
      // Unknown scheme: keep the words, drop the link.
      out.push(label);
    }
    last = start + m[0].length;
  }

  if (last < text.length) out.push(text.slice(last));
  return out.map((node, i) => <Fragment key={i}>{node}</Fragment>);
}

export default function LegalPage({ doc }: { doc: LegalDocId }) {
  const { lang, setLang, t, dateLocale } = useI18n();
  const { theme, toggle } = useTheme();

  const content = LEGAL_DOCS[doc][lang];
  const other: LegalDocId = doc === "privacy" ? "terms" : "privacy";

  // Switching between the two documents keeps the scroll offset otherwise.
  // Block body on purpose: a concise arrow would hand scrollTo's return value
  // to React as the effect's cleanup function.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [doc]);

  // A real page title matters here: these URLs are read by Google's OAuth
  // reviewers and linked from outside the app.
  useEffect(() => {
    const previous = document.title;
    document.title = `${content.title} · SplitDec`;
    return () => {
      document.title = previous;
    };
  }, [content.title]);

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-1.5 text-lg">
            <CoinMark className="h-6 w-6" />
            <Wordmark />
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
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-extrabold tracking-tight">{content.title}</h1>
        <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          {t("lastUpdated")} {formatDateOnly(LEGAL_UPDATED, dateLocale)}
        </p>

        <div className="mt-8 space-y-4 text-slate-700 dark:text-slate-300">
          {content.intro.map((p, i) => (
            <p key={i} className="leading-relaxed">
              {renderLegalText(p)}
            </p>
          ))}
        </div>

        {content.sections.map((section) => (
          <section key={section.heading} className="mt-10">
            <h2 className="text-xl font-bold tracking-tight">{section.heading}</h2>
            <div className="mt-3 space-y-4 text-slate-700 dark:text-slate-300">
              {section.blocks.map((block, i) =>
                typeof block === "string" ? (
                  <p key={i} className="leading-relaxed">
                    {renderLegalText(block)}
                  </p>
                ) : (
                  <ul key={i} className="list-disc space-y-2 pl-5 leading-relaxed marker:text-teal-600 dark:marker:text-teal-400">
                    {block.map((item, j) => (
                      <li key={j}>{renderLegalText(item)}</li>
                    ))}
                  </ul>
                ),
              )}
            </div>
          </section>
        ))}

        <nav className="mt-14 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-200 pt-6 text-sm dark:border-slate-800">
          <Link to={`/${other}`} className="font-medium text-teal-700 hover:underline dark:text-teal-300">
            {t(other === "privacy" ? "privacyPolicy" : "termsOfService")}
          </Link>
          <Link to="/" className="font-medium text-teal-700 hover:underline dark:text-teal-300">
            {t("backToApp")}
          </Link>
        </nav>
      </main>
    </div>
  );
}

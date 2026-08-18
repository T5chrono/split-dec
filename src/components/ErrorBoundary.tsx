import { Component, type ErrorInfo, type ReactNode } from "react";
import { useI18n } from "../lib/i18n";

/** Vite emits a rejected dynamic import when a chunk 404s. The wording differs
 *  per engine, so match on all three rather than one browser's phrasing. */
function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    /dynamically imported module/i.test(message) || // Chrome / Firefox
    /Importing a module script failed/i.test(message) || // Safari
    /ChunkLoadError/i.test(message)
  );
}

// A reload cannot fix a chunk that is genuinely missing, so remember when we
// last tried. Without this, a permanently-broken chunk turns into an infinite
// refresh loop, which is worse than the blank screen it replaces.
const RELOADED_AT = "splitdec.chunk-reload";
const RELOAD_COOLDOWN_MS = 15_000;

function alreadyTriedRecently(): boolean {
  try {
    const previous = Number(sessionStorage.getItem(RELOADED_AT) ?? 0);
    return Date.now() - previous < RELOAD_COOLDOWN_MS;
  } catch {
    return false; // private mode with storage disabled — one reload is fine
  }
}

function markReloadAttempt(): void {
  try {
    sessionStorage.setItem(RELOADED_AT, String(Date.now()));
  } catch {
    /* storage disabled; the cooldown just won't apply */
  }
}

/** Rendered only when a reload has already been tried and failed. */
function Fallback() {
  const { t } = useI18n();
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-xl font-bold">{t("errorBoundaryTitle")}</h1>
      <p className="max-w-md text-slate-500 dark:text-slate-400">{t("errorBoundaryBody")}</p>
      <button
        onClick={() => window.location.reload()}
        className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
      >
        {t("errorBoundaryReload")}
      </button>
    </div>
  );
}

/** Top-level boundary.
 *
 *  Exists because the routes are code-split: a client still running an old
 *  app shell after a deploy has replaced the chunk hashes will fail the next
 *  lazy import, and Suspense only covers a *pending* import, never a rejected
 *  one. Left uncaught that unmounts the tree to a blank page — a regression
 *  the single-bundle build could not have, since nothing was left to fetch.
 *
 *  A stale chunk reference is exactly what a reload fixes, so do that once and
 *  fall back to asking, rather than looping. Non-chunk errors skip the reload
 *  and go straight to the fallback: reloading them just repeats the crash.
 */
export default class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (isChunkLoadError(error) && !alreadyTriedRecently()) {
      markReloadAttempt();
      window.location.reload();
      return;
    }
    // The console is the record of last resort here: swallowing a render
    // failure silently would be worse than a noisy log.
    console.error("Unhandled error", error, info.componentStack);
  }

  render() {
    return this.state.failed ? <Fallback /> : this.props.children;
  }
}

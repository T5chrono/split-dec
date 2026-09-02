/** Error monitoring (Sentry), and the redaction that makes it admissible here.
 *
 *  Every other processor in this app receives data we chose to send it. Sentry
 *  is different: an SDK that reports crashes reports *context*, and its defaults
 *  reach for exactly the things this codebase spends the most effort keeping out
 *  of logs — the current URL, every fetch it has seen, and the markup around the
 *  last thing clicked. Three of those carry real payload here:
 *
 *    - `location.href` on the OAuth callback is `?code=<live authorization
 *      code>`, and on the recovery link `#access_token=<live credential>`.
 *      Either one in a third party's issue stream is a credential leak, not a
 *      privacy nicety.
 *    - Every `/api/...` breadcrumb spells out a group, expense or settlement id
 *      — the identifiers `insightsRoute` (src/App.tsx) and `fold_route`
 *      (api/_src/routers/reports.py) exist to keep out of measurement.
 *    - Click breadcrumbs serialize `aria-label`, `title`, `name` and `alt` off
 *      the clicked element (see `_htmlElementAsString` in @sentry/core), and
 *      `ExpensesTab` puts the expense *description* in an aria-label. Clicking
 *      "edit" on a row would otherwise ship what the user typed.
 *    - The error's own message, which none of the above covers and which this
 *      app does not write: an `ApiError` carries the `detail` string the server
 *      sent back. Nothing composes an identifier into one today, so this is the
 *      hole being closed before it opens rather than after.
 *
 *  So nothing reaches Sentry unredacted. The two hooks below are not belt and
 *  braces around a safe default; they are the only thing standing between an
 *  error report and the ledger it happened on.
 *
 *  Redaction is by *shape*, not by route list. Every id in this app is a UUID
 *  (api/_src/models.py), so matching the shape covers `/groups/<id>`,
 *  `/expenses/<id>`, `/settlements/<id>` and `/invitations/<id>` — and covers
 *  the next route without anyone remembering to come back here. That is the one
 *  place this deliberately diverges from `insightsRoute`, which folds named
 *  route patterns because its buckets have to stay readable; a crash report
 *  needs no such thing, and Sentry sees API URLs that `insightsRoute` never does.
 */

import * as Sentry from "@sentry/react";
import type { Breadcrumb, ErrorEvent } from "@sentry/react";
import { APP_ORIGIN } from "./canonicalHost";

/** Canonical UUID, the shape of every identifier this app puts in a URL. */
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

/** A scheme prefix, so a relative input comes back relative. Deliberately
 *  without the `g` flag: `.test()` on a global regex carries `lastIndex`
 *  between calls and would answer differently every other time. */
const ABSOLUTE = /^[a-z][a-z0-9+.-]*:/i;

/** `[aria-label="Edit expense: Dinner"]` → `[aria-label]`. */
const ATTRIBUTE_VALUE = /\[([a-zA-Z-]+)="[^"]*"\]/g;

/** The other identifier shape this app holds. Reaches an error message by way
 *  of an API error detail rather than anything the client composes itself. */
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

/** A URL reduced to origin and path, with identifiers blanked.
 *
 *  Query and fragment are dropped whole rather than filtered. An allow-list of
 *  safe parameters is a list somebody has to maintain against every future
 *  endpoint, and the two that matter here (`?code=`, `#access_token=`) are live
 *  credentials — the asymmetry between "lost a debugging hint" and "leaked a
 *  session" is not close. Nothing this app puts in a query string is worth it.
 *
 *  Anything that will not parse as http(s) comes back as a placeholder rather
 *  than as itself: an unrecognized string is precisely the one whose contents
 *  nobody has checked.
 */
export function redactUrl(raw: string): string {
  if (!raw) return raw;
  let url: URL;
  try {
    url = new URL(raw, APP_ORIGIN);
  } catch {
    return "[redacted]";
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return "[redacted]";
  const path = url.pathname.replace(UUID, "[id]");
  return ABSOLUTE.test(raw) ? url.origin + path : path;
}

/** A DOM breadcrumb's element path, keeping the structure and dropping the text.
 *
 *  `button.rounded-lg[aria-label="Edit expense: Dinner"]` becomes
 *  `button.rounded-lg[aria-label]`. Which control was clicked is the useful
 *  half and is all that survives; the attribute *values* are user content.
 */
export function redactSelector(selector: string): string {
  return selector.replace(ATTRIBUTE_VALUE, "[$1]");
}

/** Free text with both identifier shapes blanked.
 *
 *  Separate from `redactUrl` because the input is different in kind: that one
 *  folds a URL we constructed, while this handles text we did not write — an
 *  error message, which on this side is often a `detail` string relayed
 *  straight from the API. Stack frames are deliberately untouched; they name
 *  our own bundle and carry no values.
 */
export function redactMessage(text: string): string {
  return text.replace(UUID, "[id]").replace(EMAIL, "[email]");
}

/** Applied to every breadcrumb before it is recorded. */
export function scrubBreadcrumb(crumb: Breadcrumb): Breadcrumb {
  const scrubbed: Breadcrumb = { ...crumb };

  // ui.click / ui.input: the message is the serialized element path.
  if (scrubbed.category?.startsWith("ui.") && typeof scrubbed.message === "string") {
    scrubbed.message = redactSelector(scrubbed.message);
  }

  // fetch/xhr carry `url`; navigation carries `from` and `to`.
  if (scrubbed.data) {
    const data: Record<string, unknown> = { ...scrubbed.data };
    for (const key of ["url", "from", "to"]) {
      const value = data[key];
      if (typeof value === "string") data[key] = redactUrl(value);
    }
    scrubbed.data = data;
  }

  return scrubbed;
}

/** Applied to every event before it leaves the browser.
 *
 *  Runs over breadcrumbs a second time on purpose. `beforeBreadcrumb` covers
 *  the ones the SDK records for itself, but a breadcrumb attached directly to a
 *  scope bypasses it, and this is the last gate before the network.
 */
export function scrubEvent(event: ErrorEvent): ErrorEvent {
  if (event.request) {
    const request = { ...event.request };
    if (typeof request.url === "string") request.url = redactUrl(request.url);
    // `httpContext` fills these from the document. The referrer is an in-app
    // URL, so it names the group the user came from just as the address does.
    if (request.headers) {
      const headers: Record<string, string> = { ...request.headers };
      for (const key of Object.keys(headers)) {
        if (key.toLowerCase() === "referer") headers[key] = redactUrl(headers[key]);
      }
      request.headers = headers;
    }
    delete request.query_string;
    delete request.cookies;
    delete request.data;
    event.request = request;
  }

  if (typeof event.transaction === "string") {
    event.transaction = redactUrl(event.transaction);
  }

  // The error's own text — the one field none of the hooks above touches, and
  // the one this app does not write: an ApiError carries the `detail` string
  // the server sent, which a future endpoint could compose from a real value.
  if (event.exception?.values) {
    event.exception = {
      ...event.exception,
      values: event.exception.values.map((value) =>
        typeof value.value === "string"
          ? { ...value, value: redactMessage(value.value) }
          : value,
      ),
    };
  }

  if (typeof event.message === "string") {
    event.message = redactMessage(event.message);
  }

  if (event.breadcrumbs) {
    event.breadcrumbs = event.breadcrumbs.map(scrubBreadcrumb);
  }

  return event;
}

/** Starts error reporting, if this build was given somewhere to report to.
 *
 *  No DSN means no SDK: that is how `npm run dev`, vitest and CI stay silent
 *  without a second flag to keep in sync. The DSN is public by construction —
 *  it ships inside the bundle either way — so it lives in `.env.production`
 *  alongside the Supabase publishable key rather than in Vercel's dashboard.
 *
 *  Called from `main.tsx` rather than `App.tsx`, where the measurement products
 *  live. Two constraints pull in opposite directions and both are honoured: a
 *  crash reporter has to be installed before the first render or it misses the
 *  render that crashes, but it must not be installed on a non-canonical origin
 *  that `enforceCanonicalOrigin` is about to navigate away from. So the call
 *  sits inside `main.tsx`'s `if (!leaving)` — earlier than `App`, still behind
 *  the same guard.
 */
export function initMonitoring(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
  if (!dsn) return;

  Sentry.init({
    dsn,
    // Preview deployments and the noindex vercel.app alias serve the same
    // bundle as the apex; tagging by origin keeps their noise out of the
    // production issue stream without a build-time variable to thread through.
    environment: window.location.origin === APP_ORIGIN ? "production" : "preview",
    // No IP address, no cookies, no user identity. Errors here are diagnosed
    // from the stack, and this app has no support flow that needs "who".
    sendDefaultPii: false,
    // Errors only. `tracesSampleRate` is deliberately unset: Vercel Speed
    // Insights already measures this app's performance, and a second
    // performance processor would be another disclosure for data we have.
    beforeBreadcrumb: scrubBreadcrumb,
    beforeSend: scrubEvent,
    ignoreErrors: [
      // Fires on layout thrash in Chrome and Safari with no user-visible
      // effect and no actionable frame. Pure volume.
      /ResizeObserver loop/,
    ],
    denyUrls: [
      // Extensions run in the page and throw into our handlers. Their stacks
      // are somebody else's code and nothing here can fix them.
      /^chrome-extension:\/\//,
      /^moz-extension:\/\//,
      /^safari-(web-)?extension:\/\//,
    ],
  });
}

/** Report a caught error. A no-op when monitoring was never initialised.
 *
 *  Wrapped so `@sentry/react` is imported in exactly one module: callers say
 *  what happened, this file decides where it goes.
 */
export function reportError(error: unknown, componentStack?: string | null): void {
  Sentry.captureException(
    error,
    componentStack ? { contexts: { react: { componentStack } } } : undefined,
  );
}

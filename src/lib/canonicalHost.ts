/** Canonical-origin guard.
 *
 *  `www.split-dec.app` serves the SPA shell at `/` but 308-redirects every
 *  other path to the apex, so the app boots on www and then every same-origin
 *  `/api/*` call becomes a cross-origin hop that the CORS-less production API
 *  refuses. Requests carry an `Authorization` header, so they preflight, and a
 *  redirected preflight is a hard network error: the UI loads, login succeeds,
 *  and the first data fetch dies with "Failed to fetch".
 *
 *  `vercel.json` redirects www to the apex, but that rule has never fired for
 *  the bare root path — exactly where someone typing the domain lands. This is
 *  the client-side backstop for whatever the edge routing misses.
 *
 *  Deliberately narrow: only a `www.` host is rewritten. `split-dec.vercel.app`
 *  and preview deployments serve the API on their own origin and work fine, and
 *  an installed PWA pins its install origin — turning a *working* origin into a
 *  redirect is what caused the 2026-07-18 outage.
 */

/** The origin every outbound link must name: invitation drafts, emails, the
 *  address the landing page shows itself at. Deliberately a constant and never
 *  `location.origin` — a preview deployment or the noindex `vercel.app` alias
 *  would otherwise put a host the recipient should not be sent to into somebody
 *  else's inbox, and an installed PWA pins the origin it was installed from.
 *  Mirrors `APP_URL` in api/_src/emailer.py, which does the same for the mail
 *  the backend sends. */
export const APP_ORIGIN = "https://split-dec.app";

/** The apex equivalent of a `www.` URL, or null if already canonical. */
export function canonicalUrl(href: string): string | null {
  const url = new URL(href);
  if (!url.hostname.startsWith("www.")) return null;
  url.hostname = url.hostname.slice("www.".length);
  // Path, query and hash ride along: a link into a group must survive the hop,
  // and so must the `?code=` / `#access_token=` an auth callback arrives with.
  return url.toString();
}

/** Sends the browser to the canonical origin. Returns true if it is leaving,
 *  in which case the caller must not mount the app — `location.replace` lets
 *  the current script finish, and a mounted app would fire doomed API calls
 *  against the non-canonical origin before the navigation commits. */
export function enforceCanonicalOrigin(location: Location = window.location): boolean {
  const target = canonicalUrl(location.href);
  if (!target) return false;
  location.replace(target);
  return true;
}

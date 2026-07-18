# SplitDec — Pre-Go-Live Checklist

Things to do before treating SplitDec as a real, publicly-usable product.
The app is fully functional today at https://split-dec.vercel.app; the items
below are about production-readiness, deliverability, security hardening, and
polish — not missing features.

Status legend: ☐ not started · ◐ partial · ☑ done

---

## 1. Email deliverability (invitations + auth emails) — ◐ SMTP done, templates pending
Domain **`split-dec.app`** verified in Resend (DKIM/SPF/return-path live,
region eu-west-1). `RESEND_FROM=SplitDec <invites@split-dec.app>` and
`APP_URL=https://split-dec.app` set on Vercel production. Supabase custom
SMTP configured (smtp.resend.com:465, user `resend`, dedicated sending-only
API key, sender `auth@split-dec.app`) and **verified end-to-end**: a test
signup dispatched its confirmation email through Resend successfully
(Resend rejects recipients at reserved domains like example.com — use
`delivered@resend.dev` for tests). Custom SMTP also raised the auth email
rate limit to 30/hour.
- ☐ **Bilingual PL+EN email templates** (Authentication → Emails →
  Templates → "Confirm sign up" and "Reset password") — still Supabase's
  EN-only defaults; the dashboard Templates page was returning an internal
  error during a Supabase incident on 2026-07-18 (Site URL config on the same
  dashboard worked fine, so this looks incident-specific, not a lasting
  problem) — retry when the page loads. Suggested copy (subjects + bilingual
  HTML bodies, `{{ .ConfirmationURL }}` placeholder) was drafted in-session;
  ask Claude to regenerate it if not saved.

## 2. Google OAuth consent screen — ☐
- Confirm the Google Cloud OAuth app is **published** (not "Testing", which
  caps at 100 hand-added test users and shows an "unverified app" warning).
- Complete the OAuth consent screen (app name, logo, support email, privacy
  policy + terms URLs, authorized domains).
- Google verification may be required for the app to avoid the warning screen
  once published — plan for a few days' review.

## 3. Custom domain for the app — ◐ apex is canonical, one routing gap
- ☑ **`https://split-dec.app` (apex) is the primary domain.** A brief
  www-primary configuration (2026-07-18) caused a production incident:
  service workers registered on the apex kept serving the app shell from
  cache while `/api/*` 308-redirected to www — a cross-origin hop the
  CORS-less API correctly refuses → "Failed to fetch". SW update fetches
  also reject redirects, so apex-origin installs could never self-heal.
  **Lesson: never turn a previously-serving origin into a redirect** —
  the PWA pins its install origin.
- ☑ www → apex 308 is enforced in `vercel.json` (host-conditional redirect,
  versioned in git — the dashboard-level redirect toggle did not persist).
  `APP_URL=https://split-dec.app`.
- ☑ **Supabase Auth → URL Configuration: Site URL fixed** to
  `https://split-dec.app` (was `https://split-dec.vercel.app`) — confirmed
  by probing the verify-endpoint fallback, which now lands on the apex.
- ☐ **Known bug: the `vercel.json` www→apex redirect does not fire for the
  bare root `/`.** Confirmed with a real browser + cache-busting query
  string (not a caching artifact): `www.split-dec.app/groups/abc` correctly
  308s to the apex, but `www.split-dec.app/` (and `/?query`) serves 200
  directly from www instead of redirecting. Likely a Vercel routing-
  precedence quirk specific to the exact root path (framework/static-file
  handling may be short-circuiting the redirect check for `/` only) rather
  than a `vercel.json` syntax issue — the `has: [{type: "host", ...}]` rule
  itself is proven correct by the nested-path case. Needs investigation
  (try an explicit `/` redirect rule ahead of the `/:path*` one, or check
  Vercel's routing debug output) — low severity since anyone landing on
  `www.split-dec.app/` still gets a fully working app, just on the
  non-canonical origin.
- ☐ Google OAuth consent screen: add `split-dec.app` to authorized domains
  (the OAuth callback itself stays on the Supabase domain — no redirect URI
  change needed).

## 4. Rotate secrets that passed through chat/tooling — ☐
These were shared during development and should be rotated before launch:
- **Supabase database password** (Project Settings → Database) → update
  `DATABASE_URL` on Vercel.
- **Resend API key** (Resend → API Keys) → update `RESEND_API_KEY` on Vercel.
- Review the Supabase publishable/anon key exposure (it is public by design,
  but confirm no service-role key is anywhere in the frontend or git history).

## 5. Supabase production readiness — ☐
- **RLS stays disabled by design** (the FastAPI layer is the sole authz
  boundary; Data API grants were revoked in migration
  `20260702000001_lock_down_data_api.sql`). Re-confirm no table is reachable
  via the anon key: a quick `curl` to the REST endpoint should 401/empty.
- Free tier **pauses the project after ~1 week of inactivity** and has no
  point-in-time recovery — upgrade to Pro for uptime + daily backups before
  real users depend on it.
- Confirm the DB connection uses the **Transaction Pooler (port 6543)** in
  production `DATABASE_URL` (it does today).
- Email/password auth: enable **leaked-password protection** (HaveIBeenPwned
  check, Pro-only) and review Auth rate limits once on Pro. Keep the dashboard
  minimum password length in sync with `MIN_PASSWORD_LENGTH` in
  `src/lib/authErrors.ts` (both 8 today).

## 6. Branch protection / CI gating — ☐
- Enforcing "CI green before merge to `master`" needs GitHub Pro on a private
  repo, or making the repo public. Today the gate is by convention.
- Optionally require the Claude review to pass / be acknowledged.

## 7. Observability & error handling — ◐
- The invitation emailer now logs send failures (no more silent swallow), but
  there's no aggregated error tracking. Consider Sentry (frontend + FastAPI)
  or at least periodic review of Vercel runtime logs.
- Add a lightweight uptime check on `/api/health`.

## 8. Legal / privacy — ☐
- The app stores names, emails, avatars, and financial split data. Before a
  public launch add a Privacy Policy and Terms (also required to publish the
  Google OAuth app). Link them from the login page footer.

## 9. Funding: buycoffee.to — ☐
SplitDec will be funded by voluntary payments via [buycoffee.to](https://buycoffee.to)
rather than subscriptions or ads.
- Create a **dedicated buycoffee.to profile for SplitDec** (not a personal
  account) — separate name/avatar/description, its own payout destination,
  and a clean transaction history if this ever needs accounting for.
- Check the tax treatment of received "coffees" before relying on this
  (Poland: occasional voluntary gifts vs. recurring/business-like income can
  be treated differently — worth a quick check with an accountant rather
  than assuming, since we're not qualified to give tax advice here).
- Once the profile exists, add a support link/button in the app (footer
  and/or the account menu) pointing at the SplitDec buycoffee.to page.
- Depends on item 8 (Privacy/Terms) if the link or its landing page collects
  any user data beyond what buycoffee.to itself handles.

## 10. Android app (Play Store) via TWA — ☐ (PWA prerequisite ☑)
The app is an installable PWA (manifest + service worker; Chrome → "Add to
Home Screen"). To turn it into a Play Store app:
1. `npx @bubblewrap/cli init --manifest https://split-dec.vercel.app/manifest.webmanifest`
   (Bubblewrap offers to install JDK/Android SDK; it generates a signing key).
2. Serve `/.well-known/assetlinks.json` with the signing key's SHA-256
   fingerprint (drop the file in `public/.well-known/`) so the TWA runs
   fullscreen without the browser bar.
3. `npx @bubblewrap/cli build` → sideload the `.apk` to test, or upload the
   `.aab` to Google Play ($25 one-time developer account; privacy policy from
   item 8 is required for the listing).

## 11. Nice-to-haves before launch — ☐
- Rate limiting on write endpoints (expense/settlement/invite creation).
- Empty-state polish and a 404 page.
- `robots.txt` / basic SEO meta if the marketing page is public.
- Bundle size: the SPA is a single ~570 kB chunk; consider route-level code
  splitting if load time matters.

---

_Last updated: 2026-07-18. Maintained alongside the develop → PR → master
workflow; update statuses as items land._
